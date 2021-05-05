from flask import Flask
from flask import request,abort
from werkzeug.utils import secure_filename
import os
from utils import random_filename,seq2lines,gen_mp3
from audioSeg import audio_split
from task import ConvertTask
from threading import Thread
from uuid import uuid4
from collections import namedtuple
from time import time,sleep
import logging
from random import randint
from glob import glob
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
UPLOAD_FILE_DIR = "upload"
OUTPUT_DIR = "tmp"
LOG = logging.getLogger(__name__)


class RamStorage:
    data = {}
    unit = namedtuple("task_record",["ddl","result","delete_func"])
    
    def init(self):
        t = Thread(target=self._clean)
        t.start()
        pass

    def add(self,token,delete_func):
        ddl = time()+3600
        # ddl = time() + randint(1,10)
        record = self.unit(ddl=ddl,delete_func=delete_func,result="")
        self.data[token] = record

    def _clean(self):
        """
        Clean Outdated Task and Files every minute
        """
        while True:
            remove_ids = []
            for id,record in self.data.items():
                if record.ddl < time():
                    if callable(record.delete_func):
                        record.delete_func()
                    remove_ids.append(id)
            for id in remove_ids:
                self.data.pop(id)
            LOG.warning(f"Outdated Task Cleaned,Current Working Num: {len(self.data)} ID: {seq2lines(self.data.keys())}")
            sleep(1)

    def done(self,task_id,res):
        if task_id not in self.data:
            LOG.warning(f"task {task_id} not exist,data:{self.data}")
            return
        LOG.warning(f"task {task_id} done, result:\n{res}")
        oldrecord = self.data[task_id]
        LOG.warning(f"old record:{oldrecord}")
        newrecord = self.unit(oldrecord.ddl,res,oldrecord.delete_func)
        LOG.warning(f"new record:{newrecord}")
        self.data[task_id] = newrecord
        return
    
    def load(self,token):
        if token in self.data:
            return self.data[token]
        else:
            return None



DefaultStorage = RamStorage()

@app.route("/task",methods=["POST"])
def gen_task():
    """
    upload file to sandbox
    start the convert task
    return task_id
    filename: source_file
    """
    f = request.files.get("source_file")
    if not f:
        app.logger("No file named source_file")
        abort(400)
    token = str(uuid4())
    new_filename = token
    new_path = os.path.join(UPLOAD_FILE_DIR,new_filename)
    def delete_func():
        os.remove(new_path) # delete video file
        basename = os.path.basename(new_path)
        pathname = os.path.dirname(new_path)
        audioname = os.path.join(pathname,basename+".mp3")
        os.remove(audioname) # delete audio file
        # delete audio slice file
        parent_dir = os.path.join(os.path.dirname(pathname),UPLOAD_FILE_DIR)
        glob_pattern = os.path.join(parent_dir,basename)+"*"
        slice_files = glob(glob_pattern)
        for file in slice_files:
            os.remove(file) 
    f.save(new_path)
    t = Thread(target=split_and_convert,args=[new_path,OUTPUT_DIR])
    t.start()
    DefaultStorage.add(token,delete_func)
    return token
    

@app.route("/task/<string:task_id>",methods=["GET"])
def get_result(task_id):
    """
    """
    record = DefaultStorage.load(task_id)
    # return "get "
    if record and record.result:
        return record.result
    if not record:
        return "task not exist"
    if record and record.result=="":
        return "not ready"
    return "service error"




def split_and_convert(filename,output_dir=OUTPUT_DIR):
    token = os.path.basename(filename)
    subtask,audiofilename = gen_mp3(filename)
    subtask.wait() # split audio file from video
    files_table = audio_split(audiofilename,output_dir)
    LOG.warning(f"file table:{files_table}")
    t = ConvertTask(files_table)
    res = t.run()
    DefaultStorage.done(token,res)
    return res


if __name__=="__main__":
        app.run()

