const app = getApp();
Page({
  data: { code:'', inviteCount:0, rewardYuan:0, records:[], applyCode:'' },
  onShow(){ this.loadCode(); },
  async loadCode(){
    try{ const d=await app.get('/api/v1/referral/code'); this.setData({code:d.code,inviteCount:d.invite_count||0,rewardYuan:d.reward_yuan||0}); }
    catch(e){ console.log('加载邀请码失败', e); }
  },
  async applyReferral(){
    if(!this.data.applyCode.trim()){ wx.showToast({title:'请输入邀请码',icon:'none'}); return; }
    try{ await app.post('/api/v1/referral/apply',{code:this.data.applyCode.trim()}); wx.showToast({title:'邀请码使用成功！+50XP',icon:'success'}); this.setData({applyCode:''}); }
    catch(e){ wx.showToast({title:(e&&e.message)||'邀请码无效',icon:'none'}); }
  },
  onInput(e){ this.setData({applyCode:e.detail.value}); },
  copyCode(){
    wx.setClipboardData({data:this.data.code,success:()=>wx.showToast({title:'邀请码已复制',icon:'success'})});
  },
  shareToChat(){
    wx.showShareMenu({withShareTicket:true});
    wx.showToast({title:'点击右上角分享给好友',icon:'none'});
  },
});