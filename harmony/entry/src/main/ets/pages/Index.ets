// 梦眠阁 — 主入口 (4-Tab: 概览 | 分析 | 记录 | 我的)
import { Colors } from '../common/Constants';
import { DashboardPage } from './DashboardPage';
import { AnalysisPage } from './AnalysisPage';
import { RecordPage } from './RecordPage';
import { ProfilePage } from './ProfilePage';

@Entry
@Component
struct Index {
  @State currentTab: number = 0;
  private tabs: string[] = ['概览', '分析', '记录', '我的'];

  @Builder TabBuilder(index: number) {
    Column() {
      Text(this.tabs[index])
        .fontSize(10)
        .fontColor(this.currentTab === index ? Colors.PRIMARY : Colors.TX3)
      if (this.currentTab === index) {
        Circle({ width: 5, height: 5 })
          .fill(Colors.PRIMARY)
          .margin({ top: 3 })
      }
    }
    .justifyContent(FlexAlign.Center)
    .onClick(() => { this.currentTab = index; })
  }

  build() {
    Column() {
      Tabs({ index: this.currentTab, controller: new TabsController() }) {
        TabContent() { DashboardPage() }
        TabContent() { AnalysisPage() }
        TabContent() { RecordPage() }
        TabContent() { ProfilePage() }
      }
      .barHeight(0)
      .onChange((index: number) => { this.currentTab = index; })

      // Bottom Tab Bar
      Row() {
        ForEach(this.tabs, (tab: string, index: number) => {
          this.TabBuilder(index)
        })
      }
      .width('100%')
      .height(64)
      .backgroundColor(Colors.BG2)
      .justifyContent(FlexAlign.SpaceAround)
      .padding({ bottom: 4 })
    }
    .backgroundColor(Colors.BG)
    .width('100%')
    .height('100%')
  }
}
