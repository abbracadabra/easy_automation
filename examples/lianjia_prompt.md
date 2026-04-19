帮我写ui自动化代码，需要基于easy_automation这个框架, 框架详情请看 README.md. 

电脑环境:
adb
appium server ， 地址 localhost 4723

手机环境:
小米手机, 已开启 adb debug, 已连接


任务:
从"链家app" 获取这几个小区的信息 “远东君悦庭”  “城开珑庭” ，每个小区需要获取以下信息：
1. 最便宜的10套房子的价格
2. 




"链家app"的操作路径:
1. 打开app
2. 城市选上海
2. 点击首页上方的"二手房"
3. 最上方的搜索输入框输入小区名 XXX, 在选项里点击XXX
4. 上方“排序”选择总价从低到高
5. 获取排名前10的小区价格
6. 点击上方输入框
7. 点击输入框右边的clear 按钮, 然后输入小区名 yyy, 从步骤3重复

如果出现登录, 则抛异常error, 人类介入登录
easy_automation是我写的，不一定正确，传统ui自动化代码是线性的，而easy_automation引入了状态的概念，这减少了线性代码在ui自动化时的不稳定性
你可以用activity作为state, 也可以用ui accessibility tree里元素作为state或两者结合
default策略就是杀掉app, 重启app, 链家的package是com.homelink.android


你需要端到端闭环开发，从开发，测试验证，修改， 最终交付可运行的正确代码

代码写注释, 不要写流水账注释, 注释要精

appium capability:
{
  "platformName": "Android",
  "appium:automationName": "UiAutomator2",
  "appium:noReset": true,
  "appium:skipDeviceInitialization": true
}