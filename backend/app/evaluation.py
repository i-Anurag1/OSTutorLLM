import re
def metrics(answer,sources,gold_concepts):
    ids=set(re.findall(r'\[S(\d+)\]',answer)); valid={str(i+1) for i in range(len(sources))}; citation_precision=len(ids&valid)/len(ids) if ids else 0.0
    factual_tokens=set(re.findall(r'\b[a-zA-Z]{4,}\b',answer.lower())); source_tokens=set(re.findall(r'\b[a-zA-Z]{4,}\b',' '.join(s['text'] for s in sources).lower()))
    grounded_overlap=len(factual_tokens&source_tokens)/len(factual_tokens) if factual_tokens else 0.0
    coverage=sum(c.lower() in answer.lower() for c in gold_concepts)/len(gold_concepts) if gold_concepts else 0.0
    hallucination=max(0.0,1-grounded_overlap)
    return {'citation_correctness':round(citation_precision,3),'groundedness':round(grounded_overlap,3),'hallucination_rate_proxy':round(hallucination,3),'concept_coverage':round(coverage,3),'answer_relevance':round(coverage,3)}
