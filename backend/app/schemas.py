from pydantic import BaseModel,Field
class RegisterIn(BaseModel): email:str; password:str=Field(min_length=8,max_length=72); name:str=Field(min_length=1,max_length=120)
class LoginIn(BaseModel): email:str; password:str
class ChatIn(BaseModel): message:str=Field(min_length=2,max_length=4000); topic:str|None=None; difficulty:str='adaptive'; mode:str='teach'
class ProgressIn(BaseModel): topic:str; score:float=Field(ge=0,le=100); activity:str='quiz'
class QuizIn(BaseModel): topic:str; difficulty:str='medium'; count:int=Field(default=5,ge=1,le=20); kind:str='mcq'
class CPUIn(BaseModel): algorithm:str; processes:list[dict]; quantum:int=Field(default=2,ge=1,le=100)
class PageIn(BaseModel): algorithm:str; reference_string:list[int]; frames:int=Field(ge=1,le=20)
class BankerIn(BaseModel): allocation:list[list[int]]; maximum:list[list[int]]; available:list[int]
class DiskIn(BaseModel): algorithm:str; requests:list[int]; head:int; disk_size:int=Field(default=200,ge=2)
class SyncIn(BaseModel): buffer_size:int=Field(ge=1,le=20); items:int=Field(ge=1,le=100)
class DeadlockIn(BaseModel): allocation:list[list[int]]; request:list[list[int]]; available:list[int]
class SegIn(BaseModel): segments:list[dict]; logical:list[dict]
class ShellIn(BaseModel): script:str=Field(max_length=4000)
class PythonIn(BaseModel): source:str=Field(max_length=8000)
class CodeTestIn(BaseModel): source:str=Field(max_length=8000); expected_stdout:str=''; language:str='python'
