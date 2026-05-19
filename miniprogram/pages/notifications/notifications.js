const app = getApp();
Page({
  data: { notifications: [], unreadCount: 0, loading: true },
  onShow() { this.loadData(); },
  async loadData() {
    this.setData({ loading: true });
    try {
      const d = await app.get('/api/v1/community/notifications');
      this.setData({
        notifications: d.notifications || [],
        unreadCount: d.unread_count || 0,
        loading: false,
      });
    } catch { this.setData({ loading: false }); }
  },
  async markRead(e) {
    const id = e.currentTarget.dataset.id;
    try { await app.put('/api/v1/community/notifications/' + id + '/read'); this.loadData(); } catch {}
  },
  async markAllRead() {
    try { await app.put('/api/v1/community/notifications/read-all'); this.loadData(); } catch {}
  },
  openRelated(e) {
    const type = e.currentTarget.dataset.type;
    const relatedId = e.currentTarget.dataset.relatedId;
    const notifId = e.currentTarget.dataset.id;
    app.put('/api/v1/community/notifications/' + notifId + '/read').catch(() => {});
    if (type === 'follow') {
      wx.navigateTo({ url: '/pages/user-profile/user-profile?id=' + relatedId });
    } else if (type === 'like' || type === 'comment' || type === 'mention') {
      wx.navigateTo({ url: '/pages/post-detail/post-detail?id=' + relatedId });
    }
  },
});
