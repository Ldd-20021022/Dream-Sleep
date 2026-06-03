const app = getApp();
Page({
  data: { questions:[], current:0, selected:null, answers:{}, results:null, submitted:false, xpEarned:0, fragments:0, correctCount:0 },
  onShow(){ this.loadQuestions(); },
  async loadQuestions(){
    try{
      const d = await app.get('/api/v1/game/quiz/questions');
      this.setData({questions:d.questions||[],current:0,selected:null,answers:{},results:null,submitted:false});
    }catch{}
  },
  selectOpt(e){
    if(this.data.submitted)return;
    const idx = e.currentTarget.dataset.idx;
    const q = this.data.questions[this.data.current];
    this.data.answers[q.id] = idx;
    this.setData({selected:idx,answers:this.data.answers});
    setTimeout(()=>{
      if(this.data.current < this.data.questions.length-1){
        this.setData({current:this.data.current+1,selected:null});
      }
    },400);
  },
  prevQ(){ if(this.data.current>0) this.setData({current:this.data.current-1,selected:null}); },
  nextQ(){ if(this.data.current < this.data.questions.length-1) this.setData({current:this.data.current+1,selected:null}); },
  async submitQuiz(){
    try{
      const d = await app.post('/api/v1/game/quiz/submit',{answers:this.data.answers});
      const results = d.results || [];
      const correctCount = results.filter(function(r){return r.correct;}).length;
      this.setData({results:results,submitted:true,xpEarned:d.xp_awarded||0,fragments:d.fragments_earned||0,correctCount:correctCount});
    }catch{}
  },
  reset(){ this.loadQuestions(); },
});
