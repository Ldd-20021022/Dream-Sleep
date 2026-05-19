const app = getApp();
Page({
  data: {
    query: '', results: null, searching: false, searched: false,
    history: [],
  },
  onShow() {
    const h = wx.getStorageSync('searchHistory') || [];
    this.setData({ history: h });
  },
  onInput(e) { this.setData({ query: e.detail.value }); },
  async doSearch() {
    const q = this.data.query.trim();
    if (!q) return;
    this.setData({ searching: true, searched: true });
    try {
      const d = await app.get('/api/v1/community/search?q=' + encodeURIComponent(q));
      this.setData({ results: d, searching: false });
      // Save history
      let h = this.data.history.filter(i => i !== q);
      h.unshift(q);
      if (h.length > 10) h.pop();
      wx.setStorageSync('searchHistory', h);
      this.setData({ history: h });
    } catch {
      this.setData({ searching: false });
    }
  },
  tapHistory(e) {
    this.setData({ query: e.currentTarget.dataset.q });
    this.doSearch();
  },
  clearHistory() {
    wx.setStorageSync('searchHistory', []);
    this.setData({ history: [] });
  },
  openPost(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: '/pages/community/community?postId=' + id });
  },
  openUser(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: '/pages/user-profile/user-profile?id=' + id });
  },
});
