import math,re

def _tokens(text): return set(re.findall(r'\b[a-zA-Z]{4,}\b',text.lower()))

def metrics(answer,sources,gold_concepts):
    ids=set(re.findall(r'\[S(\d+)\]',answer)); valid={str(i+1) for i in range(len(sources))}
    citation_precision=len(ids&valid)/len(ids) if ids else 0.0
    factual=_tokens(answer); source=_tokens(' '.join(s['text'] for s in sources)); grounded=len(factual&source)/len(factual) if factual else 0.0
    coverage=sum(c.lower() in answer.lower() for c in gold_concepts)/len(gold_concepts) if gold_concepts else 0.0
    return {'citation_correctness':round(citation_precision,3),'groundedness':round(grounded,3),'hallucination_rate_proxy':round(max(0,1-grounded),3),'concept_coverage':round(coverage,3),'answer_relevance':round(coverage,3)}

def retrieval_metrics(hits,gold_sources,k=5):
    ranked=[h.get('source') for h in hits[:k]]
    gold=set(gold_sources)
    relevant=[x for x in ranked if x in gold]
    recall=len(set(relevant)&gold)/max(1,len(gold))
    rr=0.0
    for i,x in enumerate(ranked,1):
        if x in gold: rr=1/i; break
    dcg=sum((1/math.log2(i+2)) for i,x in enumerate(ranked) if x in gold)
    ideal=sum(1/math.log2(i+2) for i in range(min(len(gold),k)))
    ndcg=dcg/ideal if ideal else 0.0
    return {'recall_at_k':round(recall,3),'mrr':round(rr,3),'ndcg_at_k':round(ndcg,3)}
