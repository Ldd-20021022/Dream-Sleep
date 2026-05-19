const app = getApp();
Page({
  data: {
    userId: 0, profile: null, badges: [], loading: true,
    following: false, followLoading: false,
  },
  onLoad(options) {
    this.setData({ userId: Number(options.id) || 0 });
    this.loadProfile();
  },
  async loadProfile() {
    if (!this.data.userId) return;
    this.setData({ loading: true });
    try {
      const [profileRes, followRes, badgeRes] = await Promise.all([
        app.get('/api/v1/community/users/' + this.data.userId),
        app.get('/api/v1/community/follow/status/' + this.data.userId),
        app.get('/api/v1/community/users/' + this.data.userId + '/badges').catch(() => ({ badges: [] })),
      ]);
      this.setData({
        profile: profileRes,
        badges: (badgeRes.badges || []).filter(b => b.unlocked),
        following: followRes.following,
        loading: false,
      });
    } catch { this.setData({ loading: false }); }
  },
  async toggleFollow() {
    if (this.data.followLoading) return;
    this.setData({ followLoading: true });
    try {
      if (this.data.following) {
        await app.del('/api/v1/community/follow/' + this.data.userId);
      } else {
        await app.post('/api/v1/community/follow/' + this.data.userId);
      }
      this.setData({ following: !this.data.following });
      this.loadProfile(); // Refresh stats
    } catch { wx.showToast({ title: '操作失败', icon: 'none' }); }
    this.setData({ followLoading: false });
  },
  openPost(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: '/pages/post-detail/post-detail?id=' + id });
  },
  sendMessage() {
    wx.navigateTo({ url: '/pages/messages/messages?userId=' + this.data.userId });
  },
  blockUser() {
    wx.showActionSheet({
      itemList: ['屏蔽该用户', '举报该用户'],
      success: async (res) => {
        if (res.tapIndex === 0) {
          try {
            await app.post('/api/v1/community/block/' + this.data.userId);
            wx.showToast({ title: '已屏蔽' });
          } catch {}
        } else {
          wx.showToast({ title: '举报功能开发中' });
        }
      },
    });
  },
});
