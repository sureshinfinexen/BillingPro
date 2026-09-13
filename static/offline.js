/** Offline bill queue — localStorage backed */
window.OfflineQueue = (function(){
  const KEY = 'bp_offline_bills';
  function list(){ try{ return JSON.parse(localStorage.getItem(KEY)||'[]'); }catch(e){ return []; } }
  function save(arr){ localStorage.setItem(KEY, JSON.stringify(arr)); }
  function push(payload){
    const arr = list();
    arr.push({ id: Date.now(), payload, created: new Date().toISOString() });
    save(arr);
  }
  async function sync(){
    const arr = list();
    let ok = 0; const left = [];
    for(const item of arr){
      try{
        const r = await fetch('/api/bills',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify(item.payload)});
        const d = await r.json();
        if(d.ok) ok++; else left.push(item);
      }catch(e){ left.push(item); }
    }
    save(left);
    return ok;
  }
  return { list, push, sync };
})();
