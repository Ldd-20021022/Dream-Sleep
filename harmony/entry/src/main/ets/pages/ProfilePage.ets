// 梦眠阁 — 个人中心 (v3 MVP 简化版)
import { Colors, Spacing, Radius } from '../common/Constants';

@Component
export struct ProfilePage {
  @State guardian: object = { focus: 3, wisdom: 2, resilience: 4, vitality: 3 };

  build() {
    Scroll() {
      Column() {
        // Avatar + Name
        Column() {
          Text('😊').fontSize(36)
            .width(64).height(64).borderRadius(32)
            .backgroundColor(Colors.PRIMARY_SOFT)
            .border({ width: 2, color: Colors.PRIMARY })
            .textAlign(TextAlign.Center)
          Text('梦境旅人').fontSize(18).fontWeight(600).fontColor(Colors.TX).margin({ top: 8 })
          Text('Lv.5 · 已加入 47 天 · 连续 7 天').fontSize(12).fontColor(Colors.TEAL).margin({ top: 2 })
        }
        .margin({ top: 16, bottom: 16 })

        // Stats — cumulative
        Row() {
          this.PStat('47', '累计记录')
          this.PStat('47天', '加入梦眠阁')
          this.PStat('5/8', '徽章')
        }
        .justifyContent(FlexAlign.SpaceEvenly).width('100%')
        .margin({ bottom: 16 })

        // Guardian Attributes
        Column() {
          Text('🛡️ 守护者属性').fontSize(14).fontWeight(600).fontColor(Colors.TX).margin({ bottom: 10 })
          Row() {
            this.AttrItem('🧘', '专注', 3, Colors.PRIMARY)
            this.AttrItem('📚', '智慧', 2, Colors.TEAL)
            this.AttrItem('💪', '韧性', 4, Colors.WARN)
            this.AttrItem('⚡', '活力', 3, Colors.SUCCESS)
          }
          .justifyContent(FlexAlign.SpaceAround)
          Text('坚持记录提升专注，完成任务增长智慧').fontSize(11).fontColor(Colors.TX3).margin({ top: 8 })
        }
        .padding(16).borderRadius(Radius.XL).backgroundColor(Colors.CARD).margin({ bottom: 16 })

        // Simplified Menu — 4 items
        Column() {
          this.MenuItem('📊', '睡眠分析')
          this.MenuItem('🎯', '每日任务')
          this.MenuItem('📚', '改善课程')
          this.MenuItem('⚙️', '设置')
        }
        .borderRadius(Radius.XL).backgroundColor(Colors.CARD)

        // Logout — danger style
        Button('退出登录')
          .fontSize(14).fontColor(Colors.DANGER)
          .backgroundColor('transparent')
          .border({ width: 1, color: Colors.DANGER })
          .borderRadius(Radius.FULL)
          .width('100%').padding(14).margin({ top: 16 })
      }
      .padding(Spacing.LG)
    }
    .backgroundColor(Colors.BG)
  }

  @Builder PStat(val: string, label: string) {
    Column() {
      Text(val).fontSize(20).fontWeight(700).fontColor(Colors.TX)
      Text(label).fontSize(10).fontColor(Colors.TX3).margin({ top: 2 })
    }
  }

  @Builder AttrItem(icon: string, name: string, level: number, color: string) {
    Column() {
      Text(icon).fontSize(24)
      Text(name).fontSize(10).fontColor(Colors.TX3).margin({ top: 4 })
      Text('●'.repeat(level) + '○'.repeat(4 - level)).fontSize(14).fontColor(color).margin({ top: 2 })
    }
    .alignItems(HorizontalAlign.Center)
  }

  @Builder MenuItem(icon: string, label: string) {
    Row() {
      Text(icon).fontSize(20).width(32)
      Text(label).fontSize(14).fontColor(Colors.TX).layoutWeight(1)
      Text('→').fontSize(14).fontColor(Colors.TX3)
    }
    .padding(14).border({ width: { bottom: 1 }, color: Colors.BORDER })
  }
}
