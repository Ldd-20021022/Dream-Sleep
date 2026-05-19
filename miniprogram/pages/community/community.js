const app = getApp();

// Helpers
function timeAgo(str) {
  if (!str) return '';
  const d = new Date(str.replace(/-/g, '/'));
  if (isNaN(d.getTime())) return str.slice(0, 10);
  const diff = Math.floor((Date.now() - d.getTime()) / 1000);
  if (diff < 60) return '刚刚';
  if (diff < 3600) return Math.floor(diff / 60) + '分钟前';
  if (diff < 86400) return Math.floor(diff / 3600) + '小时前';
  if (diff < 604800) return Math.floor(diff / 86400) + '天前';
  return str.slice(0, 10);
}

function avatarColor(name) {
  if (!name) return '#6C63FF';
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  const colors = ['#6C63FF', '#E67E22', '#2ECC71', '#E74C3C', '#3498DB', '#F39C12', '#1ABC9C', '#9B59B6'];
  return colors[Math.abs(hash) % colors.length];
}

Page({
  data: {
    tab: 'highlights',
    topics: [], highlights: null,
    groups: [], challenges: [],
    leaderboard: [], lbPeriod: 'weekly',
    posts: [], recPosts: [], postContent: '', isAnonymous: false,
    postImage: '', editingPostId: null, selectedTopicId: '', selectedTopic: null,
    replyNotifications: [], notifCount: 0,
    // Post detail modal
    showDetail: false, detailPost: null, detailComments: [], commentText: '',
    replyToCommentId: 0, replyToUser: '',
    // Following
    showFollowing: false,
    // Refresh
    refreshing: false,
  },

  onShow() { this.loadAll(); },
  noop() {},

  async loadAll() {
    this.loadHighlights(); this.loadTopics(); this.loadGroups();
    this.loadChallenges(); this.loadLeaderboard();
    if (this.data.tab === 'posts') this.loadPosts();
    if (this.data.tab === 'recommended') this.loadRecommended();
    this.loadReplyNotifications();
  },

  async onPullDownRefresh() {
    this.setData({ refreshing: true });
    await this.loadAll();
    wx.stopPullDownRefresh();
    this.setData({ refreshing: false });
  },

  // ========== Highlights ==========
  async loadHighlights() {
    try { const d = await app.get('/api/v1/community/highlights'); this.setData({ highlights: d }); } catch {}
  },

  // ========== Topics ==========
  async loadTopics() {
    try { const d = await app.get('/api/v1/community/topics'); this.setData({ topics: d.topics || [] }); } catch {}
  },

  selectTopic(e) {
    const id = e.currentTarget.dataset.id;
    const topic = this.data.topics.find(t => t.id === id);
    this.setData({ selectedTopicId: id, selectedTopic: topic || null, tab: 'posts' });
    this.loadPosts();
  },
  clearTopic() {
    this.setData({ selectedTopicId: '', selectedTopic: null });
    this.loadPosts();
  },

  // ========== Groups ==========
  async loadGroups() {
    try { const d = await app.get('/api/v1/community/groups'); this.setData({ groups: d.groups || [] }); } catch {}
  },
  async joinGroup(e) {
    const id = e.currentTarget.dataset.id;
    try { await app.post(`/api/v1/community/groups/${id}/join`); wx.showToast({ title: '已加入' }); this.loadGroups(); } catch {}
  },
  async leaveGroup(e) {
    const id = e.currentTarget.dataset.id;
    try { await app.post(`/api/v1/community/groups/${id}/leave`); wx.showToast({ title: '已退出' }); this.loadGroups(); } catch {}
  },

  // ========== Challenges ==========
  async loadChallenges() {
    try { const d = await app.get('/api/v1/community/challenges'); this.setData({ challenges: d.challenges || [] }); } catch {}
  },
  async joinChallenge(e) {
    const id = e.currentTarget.dataset.id;
    try { await app.post(`/api/v1/community/challenges/${id}/join`); wx.showToast({ title: '已参加' }); this.loadChallenges(); } catch {}
  },

  // ========== Leaderboard ==========
  async loadLeaderboard() {
    try { const d = await app.get(`/api/v1/community/leaderboard?period=${this.data.lbPeriod}`); this.setData({ leaderboard: d.leaderboard || [] }); } catch {}
  },
  setPeriod(e) { this.setData({ lbPeriod: e.currentTarget.dataset.period }); this.loadLeaderboard(); },

  // ========== Tab switching ==========
  setTab(e) {
    const t = e.currentTarget.dataset.tab;
    this.setData({ tab: t, selectedTopicId: '', selectedTopic: null });
    if (t === 'posts') this.loadPosts();
    if (t === 'recommended') this.loadRecommended();
    if (t === 'leaderboard') this.loadLeaderboard();
  },

  // ========== Posts ==========
  async loadPosts() {
    try {
      let url = '/api/v1/community/posts?page=1';
      if (this.data.selectedTopicId) url += '&topic_id=' + this.data.selectedTopicId;
      const d = await app.get(url);
      this.setData({ posts: d.posts || [] });
    } catch {}
  },
  onPostInput(e) { this.setData({ postContent: e.detail.value }); },
  toggleAnon() { this.setData({ isAnonymous: !this.data.isAnonymous }); },

  async createPost() {
    if (!this.data.postContent.trim()) return;
    try {
      const body = {
        content: this.data.postContent,
        is_anonymous: this.data.isAnonymous ? 1 : 0,
        topic_id: this.data.selectedTopicId,
        image: this.data.postImage,
      };
      await app.post('/api/v1/community/posts', body);
      wx.showToast({ title: '发布成功' });
      this.setData({ postContent: '', isAnonymous: false, postImage: '' });
      this.loadPosts(); this.loadTopics();
    } catch { wx.showToast({ title: '发布失败', icon: 'none' }); }
  },

  async likePost(e) {
    const id = e.currentTarget.dataset.id;
    try {
      const res = await app.post(`/api/v1/community/posts/${id}/like`);
      if (res.liked) {
        this.setData({ animLikeId: id });
        setTimeout(() => this.setData({ animLikeId: null }), 600);
      }
      this.loadPosts();
      if (this.data.detailPost && this.data.detailPost.id === id) {
        const dp = { ...this.data.detailPost };
        dp.is_liked = res.liked;
        dp.like_count = res.liked ? (dp.like_count || 0) + 1 : Math.max(0, (dp.like_count || 0) - 1);
        this.setData({ detailPost: dp });
      }
    } catch {}
  },

  // Long press to show reaction picker
  showReactions(e) {
    const id = e.currentTarget.dataset.id;
    this.setData({ showReactionPicker: id });
  },
  hideReactions() { this.setData({ showReactionPicker: null }); },
  async sendReaction(e) {
    const postId = e.currentTarget.dataset.postId;
    const reaction = e.currentTarget.dataset.reaction;
    this.setData({ showReactionPicker: null });
    try {
      await app.post(`/api/v1/community/posts/${postId}/react`, { reaction });
      wx.showToast({ title: '已回应', icon: 'none', duration: 800 });
      this.loadPosts();
    } catch {}
  },

  // Edit post
  startEdit(e) {
    const id = e.currentTarget.dataset.id;
    const post = this.data.posts.find(p => p.id === id);
    if (post) {
      this.setData({ editingPostId: id, postContent: post.content, postImage: post.image || '' });
      this.setData({ tab: 'posts' });
    }
  },
  cancelEdit() {
    this.setData({ editingPostId: null, postContent: '', postImage: '' });
  },
  async submitEdit() {
    const id = this.data.editingPostId;
    if (!id || !this.data.postContent.trim()) return;
    try {
      await app.put(`/api/v1/community/posts/${id}`, { content: this.data.postContent });
      wx.showToast({ title: '已更新' });
      this.cancelEdit();
      this.loadPosts();
    } catch { wx.showToast({ title: '更新失败', icon: 'none' }); }
  },

  async deletePost(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '删除帖子',
      content: '确定删除？删除后无法恢复。',
      success: async (res) => {
        if (res.confirm) {
          try {
            await app.del(`/api/v1/community/posts/${id}`);
            wx.showToast({ title: '已删除' });
            this.setData({ showDetail: false, detailPost: null });
            this.loadPosts(); this.loadTopics();
          } catch { wx.showToast({ title: '删除失败', icon: 'none' }); }
        }
      },
    });
  },

  // Image upload
  chooseImage() {
    wx.chooseImage({
      count: 1, sizeType: ['compressed'],
      success: (res) => {
        wx.getFileSystemManager().readFile({
          filePath: res.tempFilePaths[0], encoding: 'base64',
          success: async (fileRes) => {
            try {
              const d = await app.post('/api/v1/community/upload', { image: fileRes.data });
              this.setData({ postImage: d.url || '' });
              wx.showToast({ title: '图片已上传' });
            } catch { wx.showToast({ title: '上传失败', icon: 'none' }); }
          },
        });
      },
    });
  },
  removeImage() { this.setData({ postImage: '' }); },

  // ========== Post Detail Modal ==========
  async openDetail(e) {
    const id = e.currentTarget.dataset.id;
    const post = this.data.posts.find(p => p.id === id);
    if (!post) return;
    this.setData({ showDetail: true, detailPost: post, detailComments: [], commentText: '' });
    try {
      const d = await app.get(`/api/v1/community/posts/${id}/comments`);
      this.setData({ detailComments: d.comments || [] });
    } catch {}
  },
  closeDetail() { this.setData({ showDetail: false, detailPost: null, detailComments: [] }); },
  onCommentInput(e) { this.setData({ commentText: e.detail.value }); },
  async sendComment() {
    if (!this.data.commentText.trim() || !this.data.detailPost) return;
    try {
      await app.post(`/api/v1/community/posts/${this.data.detailPost.id}/comment`, { content: this.data.commentText });
      wx.showToast({ title: '评论成功' });
      this.setData({ commentText: '' });
      // Reload comments
      const d = await app.get(`/api/v1/community/posts/${this.data.detailPost.id}/comments`);
      this.setData({ detailComments: d.comments || [] });
      const dp = { ...this.data.detailPost };
      dp.comment_count = (dp.comment_count || 0) + 1;
      this.setData({ detailPost: dp });
      this.loadPosts();
    } catch { wx.showToast({ title: '评论失败', icon: 'none' }); }
  },

  // ========== Reply Notifications ==========
  async loadReplyNotifications() {
    try {
      const d = await app.get('/api/v1/community/reply-notifications');
      this.setData({
        replyNotifications: d.notifications || [],
        notifCount: (d.notifications || []).length,
      });
    } catch {}
  },
  async openNotifPost(e) {
    const postId = e.currentTarget.dataset.postId;
    // Load the post and open detail
    try {
      const d = await app.get(`/api/v1/community/posts?page=1`);
      const post = (d.posts || []).find(p => p.id === postId);
      if (post) {
        this.setData({ detailPost: post, showDetail: true, detailComments: [], commentText: '' });
        const cd = await app.get(`/api/v1/community/posts/${postId}/comments`);
        this.setData({ detailComments: cd.comments || [] });
      }
    } catch {}
  },

  // ========== Recommended ==========
  async loadRecommended() {
    try {
      const d = await app.get('/api/v1/community/recommended');
      this.setData({ recPosts: d.posts || [] });
    } catch {}
  },

  // ========== Following Feed ==========
  toggleFollowing() {
    const show = !this.data.showFollowing;
    this.setData({ showFollowing: show });
    if (show) this.loadFollowingFeed();
    else this.loadPosts();
  },
  async loadFollowingFeed() {
    try {
      const d = await app.get('/api/v1/community/following-feed?page=1');
      this.setData({ posts: d.posts || [] });
    } catch {}
  },

  // ========== Bookmark ==========
  async toggleBookmark(e) {
    const id = e.currentTarget.dataset.id;
    try {
      const res = await app.post(`/api/v1/community/posts/${id}/bookmark`);
      wx.showToast({ title: res.bookmarked ? '已收藏' : '已取消收藏', icon: 'none' });
    } catch {}
  },

  // ========== Report ==========
  async reportPost(e) {
    const id = e.currentTarget.dataset.id;
    wx.showActionSheet({
      itemList: ['垃圾广告', '色情低俗', '虚假信息', '人身攻击', '其他'],
      success: async (res) => {
        const reasons = ['垃圾广告', '色情低俗', '虚假信息', '人身攻击', '其他'];
        try {
          await app.post(`/api/v1/community/posts/${id}/report`, { reason: reasons[res.tapIndex] });
          wx.showToast({ title: '举报已提交', icon: 'success' });
        } catch { wx.showToast({ title: '举报失败', icon: 'none' }); }
      },
    });
  },

  // ========== Nested Reply ==========
  replyToComment(e) {
    const commentId = e.currentTarget.dataset.commentId;
    const author = e.currentTarget.dataset.author;
    this.setData({
      replyToCommentId: commentId,
      replyToUser: author,
      commentText: '@' + author + ' ',
    });
  },
  cancelReply() {
    this.setData({ replyToCommentId: 0, replyToUser: '', commentText: '' });
  },
  async sendComment() {
    if (!this.data.commentText.trim() || !this.data.detailPost) return;
    try {
      const body = {
        content: this.data.commentText,
        parent_id: this.data.replyToCommentId,
        reply_to_user_id: this.data.replyToCommentId > 0 ? this.data.detailComments.find(
          c => c.id === this.data.replyToCommentId || (c.replies || []).some(r => r.id === this.data.replyToCommentId)
        )?.author_id || 0 : 0,
      };
      await app.post(`/api/v1/community/posts/${this.data.detailPost.id}/comment`, body);
      wx.showToast({ title: '评论成功' });
      this.setData({ commentText: '', replyToCommentId: 0, replyToUser: '' });
      const d = await app.get(`/api/v1/community/posts/${this.data.detailPost.id}/comments`);
      this.setData({ detailComments: d.comments || [] });
      const dp = { ...this.data.detailPost };
      dp.comment_count = (dp.comment_count || 0) + 1;
      this.setData({ detailPost: dp });
      this.loadPosts();
    } catch { wx.showToast({ title: '评论失败', icon: 'none' }); }
  },

  // ========== Comment Like ==========
  async likeComment(e) {
    const commentId = e.currentTarget.dataset.commentId;
    try {
      await app.post(`/api/v1/community/comments/${commentId}/like`);
      this.setData({
        detailComments: this.data.detailComments.map(c => ({
          ...c,
          like_count: c.id === commentId ? (c.like_count || 0) + 1 : c.like_count,
        })),
      });
    } catch {}
  },

  // ========== Navigation ==========
  goSearch() { wx.navigateTo({ url: '/pages/search/search' }); },
  goMessages() { wx.navigateTo({ url: '/pages/messages/messages' }); },
  goNotifications() { wx.navigateTo({ url: '/pages/notifications/notifications' }); },
  goUser(e) {
    const id = e.currentTarget.dataset.userId || e.currentTarget.dataset.id;
    if (id) wx.navigateTo({ url: '/pages/user-profile/user-profile?id=' + id });
  },
  goGroup(e) {
    const id = e.currentTarget.dataset.groupId || e.currentTarget.dataset.id;
    if (id) wx.navigateTo({ url: '/pages/group-detail/group-detail?id=' + id });
  },

  // ========== Time formatting ==========
  timeAgo: timeAgo,
  avatarColor: avatarColor,
});
