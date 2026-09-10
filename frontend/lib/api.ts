const API=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000';
export async function api(path:string,options:RequestInit={}){
 const token=typeof window!=='undefined'?localStorage.getItem('ostutor_token'):'';
 const headers=new Headers(options.headers||{});
 if(options.body && !headers.has('Content-Type')) headers.set('Content-Type','application/json');
 if(token) headers.set('Authorization',`Bearer ${token}`);
 let r:Response;
 try{r=await fetch(`${API}${path}`,{...options,headers})}catch(e){throw new Error('Cannot reach the OSTutorLLM API. Check that Docker is running and port 8000 is available.')}
 const text=await r.text(); let data:any; try{data=text?JSON.parse(text):{}}catch{data={detail:text||'Unknown server error'}}
 if(!r.ok) throw new Error((data.detail||data.error||`Request failed (${r.status})`) + ` [HTTP ${r.status}]`);
 return data;
}
export function apiBase(){return API}
