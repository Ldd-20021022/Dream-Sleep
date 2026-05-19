const app = getApp();
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
    postId: 0, post: null, comments: [], loading: true,
    commentText: '', replyToCommentId: 0, replyToUser: '',
  },
  onLoad(options) {
    this.setData({ postId: Number(options.id) || 0 });
    this.loadPost();
  },
  async loadPost() {
    if (!this.data.postId) return;
    this.setData({ loading: true });
    try {
      const [postRes, commentsRes] = await Promise.all([
        app.get('/api/v1/community/posts/' + this.data.postId),
        app.get('/api/v1/community/posts/' + this.data.postId + '/comments'),
      ]);
      this.setData({
        post: postRes.post || null,
        comments: commentsRes.comments || [],
        loading: false,
      });
    } catch { this.setData({ loading: false }); }
  },
  async likePost() {
    try {
      const res = await app.post('/api/v1/community/posts/' + this.data.postId + '/like');
      const p = { ...this.data.post };
      p.is_liked = res.liked;
      p.like_count = res.liked ? (p.like_count || 0) + 1 : Math.max(0, (p.like_count || 0) - 1);
      this.setData({ post: p });
    } catch {}
  },
  async toggleBookmark() {
    try {
      const res = await app.post('/api/v1/community/posts/' + this.data.postId + '/bookmark');
      const p = { ...this.data.post };
      p.is_bookmarked = res.bookmarked;
      this.setData({ post: p });
      wx.showToast({ title: res.bookmarked ? '已收藏' : '已取消', icon: 'none' });
    } catch {}
  },
  async toggleFollow() {
    const authorId = this.data.post?.author_id;
    if (!authorId) return;
    try {
      if (this.data.post.is_following_author) {
        await app.del('/api/v1/community/follow/' + authorId);
      } else {
        await app.post('/api/v1/community/follow/' + authorId);
      }
      const p = { ...this.data.post };
      p.is_following_author = !p.is_following_author;
      this.setData({ post: p });
    } catch {}
  },
  goUser(e) { const id = e.currentTarget.dataset.userId; if (id) wx.navigateTo({ url: '/pages/user-profile/user-profile?id=' + id }); },
  onCommentInput(e) { this.setData({ commentText: e.detail.value }); },
  async sendComment() {
    if (!this.data.commentText.trim()) return;
    try {
      const body = {
        content: this.data.commentText,
        parent_id: this.data.replyToCommentId,
      };
      await app.post('/api/v1/community/posts/' + this.data.postId + '/comment', body);
      wx.showToast({ title: '评论成功' });
      this.setData({ commentText: '', replyToCommentId: 0, replyToUser: '' });
      const d = await app.get('/api/v1/community/posts/' + this.data.postId + '/comments');
      this.setData({ comments: d.comments || [] });
    } catch { wx.showToast({ title: '评论失败', icon: 'none' }); }
  },
  replyToComment(e) {
    this.setData({
      replyToCommentId: e.currentTarget.dataset.commentId,
      replyToUser: e.currentTarget.dataset.author,
      commentText: '@' + e.currentTarget.dataset.author + ' ',
    });
  },
  cancelReply() { this.setData({ replyToCommentId: 0, replyToUser: '', commentText: '' }); },
  async likeComment(e) {
    const commentId = e.currentTarget.dataset.commentId;
    try {
      await app.post('/api/v1/community/comments/' + commentId + '/like');
    } catch {}
  },
  async sharePost() {
    try {
      const d = await app.get('/api/v1/community/posts/' + this.data.postId + '/share-card');
      wx.showShareMenu({ withShareTicket: true });
      wx.showToast({ title: '点击右上角分享', icon: 'none' });
    } catch {}
  },
  timeAgo: timeAgo,
  avatarColor: avatarColor,
});
