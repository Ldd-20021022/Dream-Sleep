const app = getApp();

Page({
  data: {
    tab: 'groups',
    groups: [],
    challenges: [],
    leaderboard: [],
    lbPeriod: 'weekly',
    posts: [],
    postContent: '',
    isAnonymous: false,
  },

  onShow() { this.loadAll(); },

  async loadAll() {
    this.loadGroups();
    this.loadChallenges();
    this.loadLeaderboard();
    this.loadPosts();
  },

  async loadGroups() {
    try { const data = await app.get('/api/v1/community/groups'); this.setData({ groups: data.groups || [] }); } catch {}
  },
  async loadChallenges() {
    try { const data = await app.get('/api/v1/community/challenges'); this.setData({ challenges: data.challenges || [] }); } catch {}
  },
  async loadLeaderboard() {
    try { const data = await app.get(`/api/v1/community/leaderboard?period=${this.data.lbPeriod}`); this.setData({ leaderboard: data.leaderboard || [] }); } catch {}
  },
  async loadPosts() {
    try { const data = await app.get('/api/v1/community/posts?page=1'); this.setData({ posts: data.posts || [] }); } catch {}
  },

  setTab(e) { this.setData({ tab: e.currentTarget.dataset.tab }); },
  setPeriod(e) { this.setData({ lbPeriod: e.currentTarget.dataset.period }); this.loadLeaderboard(); },

  async joinGroup(e) {
    const id = e.currentTarget.dataset.id;
    try { await app.post(`/api/v1/community/groups/${id}/join`); wx.showToast({ title: '已加入' }); this.loadGroups(); } catch {}
  },
  async leaveGroup(e) {
    const id = e.currentTarget.dataset.id;
    try { await app.post(`/api/v1/community/groups/${id}/leave`); wx.showToast({ title: '已退出' }); this.loadGroups(); } catch {}
  },
  async joinChallenge(e) {
    const id = e.currentTarget.dataset.id;
    try { await app.post(`/api/v1/community/challenges/${id}/join`); wx.showToast({ title: '已参加' }); this.loadChallenges(); } catch {}
  },

  onPostInput(e) { this.setData({ postContent: e.detail.value }); },
  toggleAnon() { this.setData({ isAnonymous: !this.data.isAnonymous }); },
  async createPost() {
    if (!this.data.postContent.trim()) return;
    try {
      await app.post('/api/v1/community/posts', { content: this.data.postContent, is_anonymous: this.data.isAnonymous ? 1 : 0 });
      wx.showToast({ title: '发布成功' });
      this.setData({ postContent: '', isAnonymous: false });
      this.loadPosts();
    } catch {}
  },
  async likePost(e) {
    const id = e.currentTarget.dataset.id;
    try { await app.post(`/api/v1/community/posts/${id}/like`); this.loadPosts(); } catch {}
  },
});
