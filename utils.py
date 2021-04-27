import hashlib
import hmac
import yaml
import subprocess
import logging
import time
import base64
import requests
import os

LOG = logging.getLogger(__name__)


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



def md5(payload: str)->str:
    """MD5 encode
    params:
        payload: 
    """
    return hashlib.md5(payload.encode('utf8')).digest().hex()

def sha1(payload:str,key:str="")->str:
    """
    sha1 encode
    params:
        payload: 
        key: 可选的秘钥，若留空，则仅进行sha1加密
    """
    if not key:
        return hashlib.sha1(payload.encode()).hexdigest()
    return hmac.new(key.encode(),payload.encode(),hashlib.sha1).hexdigest()


class signatureGenerator:
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
        return base64.encodebytes(sha1_token.encode()).decode()

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

# def seperate(filename):

class APIClient:
    baseURL = "http://raasr.xfyun.cn/api/"
    config  = Config()
    signa = signatureGenerator(**config.SDK)
    def prepare(self,filename):
        stat = os.stat(filename)
        params = {
            "app_id":"",
            "signa":self.signa(),
            "ts":APIClient.get_time(),
            "file_len":stat.st_size,
            "file_name":filename,
            "slice_num":1
        }
        params.update(self.config.SDK)
        return self._call_api("prepare",params)

    def _call_api(self,aciton,params,form=False):
        headers = {}
        if form:
            headers.update({"Content-Type":"multipart/form-data;"})
        LOG.warning(f"call_api params: {params} headers:{headers}")
        resp = requests.post(self.baseURL+aciton,data=params,headers=headers)
        return json.loads(resp.text)

    @staticmethod
    def get_time():
        """
        返回unix second timestamp
        """
        return str(int(time.time()))

    




if __name__=="__main__":
    client =APIClient()
    client.baseURL = "http://localhost:6543/"
    client.prepare("a.mp3")

