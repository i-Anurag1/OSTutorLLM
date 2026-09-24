import sys
sys.path.insert(0,'backend')
from app.rag import ingest_all,retrieve
from app.simulators import cpu_scheduling,page_replacement,bankers,disk_scheduling,producer_consumer,dining_philosophers,paging,segmentation,thread_lifecycle
r=ingest_all(); assert r['sources']>=16 and r['chunks']>=16
assert retrieve('page replacement FIFO LRU Optimal',3)
assert cpu_scheduling('Round Robin',[{'pid':'P1','arrival':0,'burst':4,'priority':1}],2)['metrics']
assert page_replacement('LRU',[1,2,1],2)['faults']==2
assert bankers([[0,1,0],[2,0,0],[3,0,2],[2,1,1],[0,0,2]],[[7,5,3],[3,2,2],[9,0,2],[4,2,2],[5,3,3]],[3,3,2])['safe']
assert disk_scheduling('SSTF',[98,183,37,122,14,124,65,67],53)['order']
assert producer_consumer(3,4)['events']
assert dining_philosophers()['deadlock_free_ordered']
assert paging([10,11],4,4)['rows']
assert segmentation([{'base':100,'limit':50}],[{'segment':0,'offset':20}])['rows'][0]['valid']
assert thread_lifecycle()['states']
print('OSTutorLLM self-test: PASS')
