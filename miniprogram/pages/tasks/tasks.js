const app = getApp();

Page({
  data: {
    todayTasks: [],
    compIds: [],
    badges: [],
    points: 0,
    loading: true,
  },

  onShow() { this.loadData(); },

  dateKey() {
    const d = new Date();
    return `${d.getFullYear()}-${d.getMonth()+1}-${d.getDate()}`;
  },

  async loadData() {
    this.setData({ loading: true });
    try {
      const [tasksRes, badgesRes, pointsRes] = await Promise.all([
        app.get('/api/v1/tasks/today').catch(() => ({ tasks: [] })),
        app.get('/api/v1/tasks/badges').catch(() => []),
        app.get('/api/v1/tasks/points/summary').catch(() => ({ total_points: 0 })),
      ]);

      const tasks = tasksRes.tasks || tasksRes || [];
      const completions = await app.get(`/api/v1/tasks/${this.dateKey()}`).catch(() => []);
      const compIds = (completions || []).map(c => c.task_id);

      this.setData({
        todayTasks: tasks,
        compIds,
        badges: badgesRes || [],
        points: (pointsRes.total_points || 0),
        loading: false,
      });
    } catch { this.setData({ loading: false }); }
  },

  async toggleTask(e) {
    const taskId = e.currentTarget.dataset.id;
    const dk = this.dateKey();
    try {
      if (this.data.compIds.includes(taskId)) {
        await app.del('/api/v1/tasks/complete', { task_id: taskId, date_key: dk });
        this.setData({ compIds: this.data.compIds.filter(id => id !== taskId) });
      } else {
        await app.post('/api/v1/tasks/complete', { task_id: taskId, date_key: dk });
        this.setData({ compIds: [...this.data.compIds, taskId] });
      }
      // Refresh points
      const pts = await app.get('/api/v1/tasks/points/summary').catch(() => ({ total_points: 0 }));
      this.setData({ points: pts.total_points || 0 });
    } catch {}
  },
});
