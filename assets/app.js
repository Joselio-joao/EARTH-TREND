
function addInvestigation(){
 const name=document.getElementById('iname').value.trim()||'Untitled investigation';
 const region=document.getElementById('iregion').value, theme=document.getElementById('itheme').value, stage=document.getElementById('istage').value;
 const tr=document.createElement('tr');
 [name,region,theme,stage].forEach((v,i)=>{const td=document.createElement('td');if(i===0){td.className='datasetname';td.textContent=v}else if(i===3){const span=document.createElement('span');span.className='pill gray';span.textContent=v;td.appendChild(span)}else td.textContent=v;tr.appendChild(td)});
 document.getElementById('investigationRows').prepend(tr);
}
