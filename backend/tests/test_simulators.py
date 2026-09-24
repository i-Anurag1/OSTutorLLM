from app.simulators import *
def test_fcfs(): assert cpu_scheduling('FCFS',[{'pid':'P1','arrival':0,'burst':3},{'pid':'P2','arrival':1,'burst':2}])['avg_waiting']==1.0
def test_rr(): assert len(cpu_scheduling('Round Robin',[{'pid':'P1','arrival':0,'burst':5},{'pid':'P2','arrival':0,'burst':3}],2)['timeline'])==5
def test_lru(): assert page_replacement('LRU',[1,2,1,3],2)['faults']==3
def test_optimal(): assert page_replacement('Optimal',[1,2,3,1,2,4],3)['faults']==4
def test_banker(): assert bankers([[0,1,0],[2,0,0],[3,0,2]],[[7,5,3],[3,2,2],[9,0,2]],[3,3,2])['safe'] is False
def test_disk(): assert disk_scheduling('FCFS',[98,183,37],53)['order']==[98,183,37]
def test_paging(): assert paging([10,11],4,4)['rows'][0]['page']==2
def test_seg(): assert segmentation([{'base':100,'limit':50}],[{'segment':0,'offset':20}])['rows'][0]['physical']==120
