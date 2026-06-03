const app = getApp();

function avatarColor(name) {
  if (!name) return '#6C63FF';
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  const colors = ['#6C63FF', '#E67E22', '#2ECC71', '#E74C3C', '#3498DB', '#F39C12', '#1ABC9C', '#9B59B6'];
  return colors[Math.abs(hash) % colors.length];
}

Page({
  data: {
    leaderboard: [],
    lbPeriod: 'weekly',
    refreshing: false,
  },

  onShow() { this.loadLeaderboard(); },

  async onPullDownRefresh() {
    this.setData({ refreshing: true });
    await this.loadLeaderboard();
    wx.stopPullDownRefresh();
    this.setData({ refreshing: false });
  },

  async loadLeaderboard() {
    try {
      const d = await app.get('/api/v1/community/leaderboard?period=' + this.data.lbPeriod);
      this.setData({ leaderboard: d.leaderboard || [] });
    } catch {}
  },

  setPeriod(e) {
    this.setData({ lbPeriod: e.currentTarget.dataset.period });
    this.loadLeaderboard();
  },

  avatarColor: avatarColor,
});
