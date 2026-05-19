const app = getApp();
Page({
  data: { worries:[], input:'', bubbles:[], popped:0, xpEarned:0, phase:'write' },
  onInput(e){ this.setData({input:e.detail.value}); },
  addWorry(){
    const w = this.data.input.trim();
    if(!w || this.data.worries.length>=10) return;
    this.data.worries.push(w);
    this.setData({worries:this.data.worries,input:''});
  },
  startCrush(){
    if(this.data.worries.length===0) return;
    const bubbles = this.data.worries.map((w,i)=>({id:i,text:w,x:20+Math.random()*60+'%',y:20+Math.random()*50+'%',size:0.8+Math.random()*0.4,delay:i*0.2+'s',popped:false}));
    this.setData({phase:'crush',bubbles:bubbles,popped:0});
  },
  popBubble(e){
    const id = e.currentTarget.dataset.id;
    const bubbles = this.data.bubbles;
    const b = bubbles.find(x=>x.id===id);
    if(!b||b.popped)return;
    b.popped=true;
    const popped = this.data.popped+1;
    this.setData({bubbles,popped});
    if(popped>=bubbles.length){ this._finish(); }
  },
  async _finish(){
    try{
      const d = await app.post('/api/v1/game/worry/submit',{count:this.data.worries.length});
      this.setData({xpEarned:d.xp_awarded||0,phase:'done'});
    }catch{this.setData({phase:'done',xpEarned:this.data.worries.length*3});}
  },
  reset(){ this.setData({worries:[],input:'',bubbles:[],popped:0,xpEarned:0,phase:'write'}); },
});