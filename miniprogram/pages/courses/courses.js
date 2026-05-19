const app = getApp();
Page({
  data: { courses: [], viewing: null, chapters: [] },
  onShow() { this.loadCourses(); },
  async loadCourses() { try { const data = await app.get('/api/v1/courses'); this.setData({ courses: data.courses || [] }); } catch {} },
  async viewCourse(e) {
    const id = e.currentTarget.dataset.id; const course = this.data.courses.find(c => c.id === id);
    this.setData({ viewing: course }); try { const data = await app.get('/api/v1/courses/' + id + '/chapters'); this.setData({ chapters: data.chapters || [] }); } catch {}
  },
  async enrollCourse(e) { const id = e.currentTarget.dataset.id; await app.post('/api/v1/courses/' + id + '/enroll'); wx.showToast({ title: '报名成功' }); },
  closeView() { this.setData({ viewing: null, chapters: [] }); },
});
