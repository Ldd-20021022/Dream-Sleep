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
Page({
  data: {
    groupId: 0, group: null, members: [], posts: [],
    loading: true, isMember: false,
    postContent: '', postImage: '', posting: false,
  },
  onLoad(options) {
    this.setData({ groupId: Number(options.id) || 0 });
    this.loadDetail();
  },
  async loadDetail() {
    if (!this.data.groupId) return;
    this.setData({ loading: true });
    try {
      const [groupRes, postsRes] = await Promise.all([
        app.get('/api/v1/community/groups/' + this.data.groupId),
        app.get('/api/v1/community/groups/' + this.data.groupId + '/posts'),
      ]);
      this.setData({
        group: groupRes.group, members: groupRes.members || [],
        posts: postsRes.posts || [],
        isMember: groupRes.group ? groupRes.group.is_member : false,
        loading: false,
      });
    } catch { this.setData({ loading: false }); }
  },
  async toggleJoin() {
    const id = this.data.groupId;
    try {
      if (this.data.isMember) {
        await app.post('/api/v1/community/groups/' + id + '/leave');
      } else {
        await app.post('/api/v1/community/groups/' + id + '/join');
      }
      this.setData({ isMember: !this.data.isMember });
      this.loadDetail();
      wx.showToast({ title: this.data.isMember ? '已退出' : '已加入' });
    } catch {}
  },
  onPostInput(e) { this.setData({ postContent: e.detail.value }); },
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
            } catch {}
          },
        });
      },
    });
  },
  async createPost() {
    if (!this.data.postContent.trim() && !this.data.postImage) return;
    if (this.data.posting) return;
    this.setData({ posting: true });
    try {
      await app.post('/api/v1/community/posts', {
        content: this.data.postContent,
        image: this.data.postImage,
        group_id: this.data.groupId,
      });
      wx.showToast({ title: '发布成功' });
      this.setData({ postContent: '', postImage: '', posting: false });
      this.loadDetail();
    } catch { this.setData({ posting: false }); wx.showToast({ title: '发布失败', icon: 'none' }); }
  },
  openPost(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: '/pages/post-detail/post-detail?id=' + id });
  },
  timeAgo: timeAgo,
});
