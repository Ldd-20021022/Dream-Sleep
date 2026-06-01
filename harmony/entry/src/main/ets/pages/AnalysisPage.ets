// 梦眠阁 — 睡眠分析 (评分拆解 + AI报告)
import { Colors, Spacing, Radius } from '../common/Constants';

@Component
export struct AnalysisPage {
  @State period: number = 30;

  build() {
    Scroll() {
      Column() {
        Text('睡眠分析').fontSize(18).fontWeight(600).fontColor(Colors.TX).margin({ bottom: 16 })

        // Score Breakdown
        Column() {
          Text('📊 昨晚评分怎么来的').fontSize(14).fontWeight(600).fontColor(Colors.TX).margin({ bottom: 10 })
          this.BreakdownRow('⏱️ 时长 7.5h / 目标 8h', '40/40')
          this.BreakdownRow('⭐ 质量 4/5', '24/30')
          this.BreakdownRow('🏷️ 标签 深睡 · 无负面', '12/15')
          Row() {
            Text('总分').fontSize(14).fontWeight(700).fontColor(Colors.TEAL)
            Blank()
            Text('82 分').fontSize(14).fontWeight(700).fontColor(Colors.TEAL)
          }
          .padding({ top: 8 })
        }
        .padding(16).borderRadius(Radius.XL).backgroundColor(Colors.CARD)

        // Period toggle
        Row() {
          this.PeriodBtn('7天', 7)
          this.PeriodBtn('14天', 14)
          this.PeriodBtn('30天', 30)
        }
        .padding(4).borderRadius(10).backgroundColor(Colors.CARD)
        .margin({ top: 16 })

        // Metrics
        Grid() {
          GridItem() { this.MetricCard('月均时长', '7.3h', '↑ 0.5h') }
          GridItem() { this.MetricCard('月均评分', '76', '↑ 8分', Colors.TEAL) }
          GridItem() { this.MetricCard('睡眠效率', '91%', '良好', Colors.WARN) }
          GridItem() { this.MetricCard('规律度', '规则', '±18min', Colors.TEAL) }
        }
        .columnsTemplate('1fr 1fr').rowsGap(10).columnsGap(10).margin({ top: 16 })

        // AI Report
        Column() {
          Text('🤖 AI 深度分析').fontSize(14).fontWeight(600).fontColor(Colors.TX).margin({ bottom: 10 })
          Text('📊 整体趋势：近30天睡眠评分持续上升，从68分提升到82分。时长稳定在7-8小时。')
            .fontSize(12).fontColor(Colors.TX2).lineHeight(20).margin({ bottom: 6 })
          Text('🎯 核心发现：周二/四评分偏低与工作日压力相关。规律度良好表明你的生物钟在逐步校准。')
            .fontSize(12).fontColor(Colors.TX2).lineHeight(20).margin({ bottom: 6 })
          Text('💡 本周建议：① 保持23:00入睡节奏 ② 周三加一次户外运动 ③ 尝试睡前热水浴')
            .fontSize(12).fontColor(Colors.TX2).lineHeight(20).margin({ bottom: 6 })
          Text('🌟 进步：睡眠效率从85%提升到91%，深睡比例增加明显。')
            .fontSize(12).fontColor(Colors.TEAL).lineHeight(20)
        }
        .padding(16).borderRadius(Radius.XL).backgroundColor(Colors.CARD).margin({ top: 16 })
      }
      .padding(Spacing.LG)
    }
    .backgroundColor(Colors.BG)
  }

  @Builder BreakdownRow(label: string, score: string) {
    Row() {
      Text(label).fontSize(12).fontColor(Colors.TX2)
      Blank()
      Text(score).fontSize(12).fontColor(Colors.TX2)
    }
    .padding({ top: 5, bottom: 5 })
    .border({ width: { bottom: 1 }, color: 'rgba(255,255,255,0.04)' })
  }

  @Builder MetricCard(label: string, value: string, sub: string, valColor?: string) {
    Column() {
      Text(label).fontSize(10).fontColor(Colors.TX3)
      Text(value).fontSize(22).fontWeight(700).fontColor(valColor || Colors.TX).margin({ top: 4 })
      Text(sub).fontSize(10).fontColor(Colors.TX3).margin({ top: 2 })
    }
    .padding(14).borderRadius(Radius.LG).backgroundColor(Colors.CARD)
    .justifyContent(FlexAlign.Center)
  }

  @Builder PeriodBtn(label: string, days: number) {
    Button(label)
      .fontSize(13)
      .backgroundColor(this.period === days ? Colors.PRIMARY : 'transparent')
      .fontColor(this.period === days ? '#fff' : Colors.TX2)
      .borderRadius(8).layoutWeight(1).padding(8)
      .onClick(() => { this.period = days; })
  }
}
