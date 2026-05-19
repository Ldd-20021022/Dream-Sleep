const app = getApp();
Page({
  data: { status: null, achievements: [], leaderboard: [], unlockedCount: 0 },
  onShow() { this.loadAll(); },
  async loadAll() {
    try {
      const [s, a, l] = await Promise.all([app.get('/api/v1/game/status'), app.get('/api/v1/game/achievements'), app.get('/api/v1/game/leaderboard')]);
      const ach = a.achievements || [];
      const unlocked = ach.filter(function(x) { return x.unlocked; }).length;
      this.setData({ status: s, achievements: ach, leaderboard: l.leaderboard || [], unlockedCount: unlocked });
    } catch {}
  },
  async checkin() {
    try { const data = await app.post('/api/v1/game/checkin'); wx.showToast({ title: data.message }); this.loadAll(); }
    catch { wx.showToast({ title: '今日已签到', icon: 'none' }); }
  },
  async checkAchievements() {
    try { const data = await app.post('/api/v1/game/achievements/check'); wx.showToast({ title: '解锁 ' + ((data.new_unlocks && data.new_unlocks.length) || 0) + ' 个成就' }); this.loadAll(); }
    catch {}
  },
});
