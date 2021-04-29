import hashlib
import hmac
import yaml
import subprocess
import logging
import time
import base64
import requests
import os
import json
import srt
from datetime import timedelta

LOG = logging.getLogger(__name__)

def parse_malformed_json(text):
    res = json.loads(text)
    for k,v in res.items():
        if isinstance(v,dict):
            res[k] = parse_malformed_json(v)
        if isinstance(v,str):
            res[k] = _parse_malformed_json(v)
    return res

def _parse_malformed_json(text):
    try:
        d = json.loads(text)
    except:
        return text
    return d

def millisec2delta(begin,base_seconds=0):
    """
    base_seconds: 秒
    begin: 毫秒
    返回一个timedelta对象
    """
    if isinstance(begin,str):
        begin = int(begin)
    seconds = begin//1000 + base_seconds
    milliseconds = begin - (begin//1000)*1000
    return timedelta(0,seconds,milliseconds=milliseconds)

def md5(payload: str)->str:
    """MD5 encode
    params:
        payload: 
    """
    return hashlib.md5(payload.encode('utf8')).hexdigest()

def sha1(payload:str,key:str="")->bytes:
    """
    sha1 encode
    params:
        payload: 
        key: 可选的秘钥，若留空，则仅进行sha1加密
    """
    if not key:
        return hashlib.sha1(payload.encode()).digest()
    return hmac.new(key.encode(),payload.encode(),hashlib.sha1).digest() 

def gen_mp3(filename,newbase)->subprocess.Popen:
    """
    gen mp3 file from video file
    params:
        filename: source video file
        newbase: the basename of new mp3 file
    return:
        Popen object
    """
    return subprocess.Popen(f"ffmpeg -i {filename} {newbase+'.mp3'}",shell=True)

class Config:
    flattend = {}
    data = {}
    def __init__(self,filename="conf.yml"):
        self.data = self.load_config(filename)
        self._flatten(self.data,self.flattend)
    
    def __getattr__(self,key):
        if key.lower() in self.data or key.upper() in self.data:
            return self.data.get(key.lower()) or self.data.get(key.upper())
    
    def _flatten(self,config,d):
        if isinstance(config,dict):
            for k,v in config.items():
                if isinstance(v,dict):
                    d.update(self._flatten(v,d))
                else:
                    d[k]=v
        return d    
    @staticmethod
    def load_config(filename):
        return yaml.load(open(filename,"r"),yaml.loader.Loader)

class SignatureGenerator:
    def __init__(self,app_id,secret_key,**kwargs):
        self.appid = app_id or ""
        self.secret = secret_key or ""
        self.logger = logging.getLogger("")
        LOG.warning("using APPID:%s SECRET:%s",self.appid,self.secret)

    
    def __call__(self):
        # baseString = appid + ts
        # signa = Base64Encode(HmacSha1(md5(baseString),key)))
        base_string = self.appid + str(int(time.time()))
        md5_token = md5(base_string)
        sha1_token = sha1(md5_token,self.secret)
        return base64.encodebytes(sha1_token).decode()[:-1]

class SliceIdGenerator:
    """slice id生成器"""

    def __init__(self):
        self.__ch = 'aaaaaaaaa`'

    def getNextSliceId(self):
        ch = self.__ch
        j = len(ch) - 1
        while j >= 0:
            cj = ch[j]
            if cj != 'z':
                ch = ch[:j] + chr(ord(cj) + 1) + ch[j + 1:]
                break
            else:
                ch = ch[:j] + 'a' + ch[j + 1:]
                j = j - 1
        self.__ch = ch
        return self.__ch

class ConvertAPIClient:
    baseURL = "http://raasr.xfyun.cn/api/"
    config  = Config()
    signa = SignatureGenerator(**config.SDK)
    
    def __call__(self,filename):
        task_id = self.prepare(filename)
        self.upload(filename,task_id)
        self.merge(task_id)
        self.get_progress(task_id)
        data = self.get_result(task_id).get("data",[])
        return self.compose(data)


    def prepare(self,filename):
        stat = os.stat(filename)
        params = {
            "app_id":"",
            "signa":self.signa(),
            "ts":self.get_time(),
            "file_len":stat.st_size,
            "file_name":filename,
            "slice_num":1
        }
        params.update(self.config.SDK)
        res = self._call_api("prepare",params)
        if res.get("ok",-1)!=0:
            LOG.fatal(f"error prepare {filename} res:{res}")
        task_id = res.get("data","")
        LOG.warning(f"filename:{filename} -> task_id {task_id}")
        return task_id
        

    def upload(self,filename,task_id):
        params = {
            "app_id":"",
            "signa":self.signa(),
            "ts":self.get_time(),
            "slice_id":"aaaaaaaaaa",
            "task_id":task_id
        }
        params.update(self.config.SDK)
        files = {"filename":"aaaaaaaaa","content":self._piece(filename)}
        return self._call_api("upload",params,files=files)

    def merge(self,task_id):
        params = {
            "ts":self.get_time(),
            "signa":self.signa(),
            "task_id":task_id
        }
        params.update(self.config.SDK)
        return self._call_api("merge",params=params)

    def get_progress(self,task_id):
        params = {
            "ts":self.get_time(),
            "signa":self.signa(),
            "task_id":task_id
        }
        params.update(self.config.SDK)
        res = self._call_api("getProgress",params=params)
        retry = 100
        while retry!=0:
            print(res)
            data = res.get("data",{}) or {}
            status = data.get("status",-1)
            if status==-1:
                LOG.error(f"上传失败,res:{res}")
                return task_id,False
            elif status == 0:
                LOG.error(f"创建成功,data:{data}")
            elif status == 9:
                LOG.error(f"任务完成,data:{data}")
                return task_id,True
            else:
                LOG.error(f"转写中 a:{data}")
            time.sleep(1)
            retry = retry - 1
            LOG.warning(f"重试第{100-retry+1}次")
            res = self._call_api("getProgress",params=params)
        return task_id,retry!=0

    def get_result(self,task_id):
        params = {
            "ts":self.get_time(),
            "signa":self.signa(),
            "task_id":task_id
        }
        params.update(self.config.SDK)
        return self._call_api("getResult",params=params)

    @staticmethod
    def _piece(filename,len=1024*1024*10):
        # file_len = os.stat(filename).st_size
        # while file_len-len>0:
        with open(filename,"rb") as f:
            return f.read()
      
    def _call_api(self,action,params={},**kwargs):
        LOG.warning(f"call_api {action} params: {params}")
        resp = requests.post(self.baseURL+action,data=params,**kwargs)
        res = json.loads(resp.text)
        if res.get("ok",-1)!=0:
            LOG.error(f"call_api {action} failed ,result: {res}")
        return parse_malformed_json(resp.text)

    @staticmethod
    def get_time():
        """
        返回unix second timestamp
        """
        return str(int(time.time()))

    @staticmethod
    def compose(res_slices):
        subs = []
        for index,res_slice in enumerate(res_slices):
            start = millisec2delta(res_slice.get("bg",0))
            end = millisec2delta(res_slice.get("ed",0))
            title = srt.Subtitle(index=index,start = start,end=end,content=res_slice.get("onebest",""))
            subs.append(title)
        return subs
    




if __name__=="__main__":
    convert =ConvertAPIClient()
    print(convert(filename="a_001.mp3"))

