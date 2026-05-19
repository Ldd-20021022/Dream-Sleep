const app = getApp();
Page({
  data: { adventure:null, battling:false, battleResult:null },
  onShow(){ this.loadAdventure(); },
  async loadAdventure(){
    try{ const d=await app.get('/api/v1/game/adventure'); this.setData({adventure:d}); }catch{}
  },
  startBattle(e){
    const ch = e.currentTarget.dataset.chapter;
    this.setData({battling:true,battleChapter:ch,battleHP:100,battleText:''});
    this._animateBattle(ch);
  },
  _animateBattle(ch){
    const chData = this.data.adventure.chapters.find(c=>c.chapter===ch);
    if(!chData) return;
    let hp = 100;
    const steps = ['🔹 使用CBT-I技能...','💪 认知重构！识别负面想法...','🎯 刺激控制！坚定信念...','⚡ 释放放松技巧...',`💥 击败了${chData.boss}！`];
    let i=0;
    const timer = setInterval(()=>{
      if(i>=steps.length){ clearInterval(timer); this._finishBattle(ch); return; }
      hp -= 25;
      this.setData({battleHP:Math.max(0,hp),battleText:steps[i]});
      i++;
    },800);
  },
  async _finishBattle(ch){
    try{
      const d=await app.post('/api/v1/game/adventure/battle',{chapter:ch});
      this.setData({battling:false,battleResult:d, battleHP:0, battleText:`🎉 ${d.message}`});
      this.loadAdventure();
    }catch{ this.setData({battling:false}); }
  },
});