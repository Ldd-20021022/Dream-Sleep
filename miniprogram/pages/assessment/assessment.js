const app = getApp();
Page({
  data: { scales: [], selected: null, questions: [], answers: {}, result: null, loading: false },
  onShow() { app.get('/api/v1/wellness/assessments').then(d => this.setData({ scales: d.scales || [] })).catch(() => {}); },
  selectScale(e) {
    const id = e.currentTarget.dataset.id;
    this.setData({ selected: id, answers: {}, result: null });
    app.get('/api/v1/wellness/assessments/' + id).then(d => this.setData({ questions: d.questions || [] })).catch(() => {});
  },
  setAnswer(e) {
    const qid = String(e.currentTarget.dataset.qid);
    const val = e.currentTarget.dataset.val;
    const answers = { ...this.data.answers, [qid]: parseInt(val) };
    this.setData({ answers });
  },
  async submit() {
    this.setData({ loading: true });
    try { const data = await app.post('/api/v1/wellness/assessments/' + this.data.selected + '/submit', { answers: this.data.answers }); this.setData({ result: data }); } catch {}
    this.setData({ loading: false });
  },
  goBack() { this.setData({ selected: null, questions: [], answers: {}, result: null }); },
});
