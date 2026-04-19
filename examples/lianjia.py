"""
链家 App 自动化: 获取指定小区最便宜房源价格
基于 easy_automation 状态机 + Appium UiAutomator2

状态机处理页面导航和异常恢复（弹窗、登录、迷路），
业务逻辑（输入小区名、排序、抓价格）在 goto 之间用 Appium 直接操作。

状态:
  login          → 登录页（抛异常，人工介入）
  main_page      → 链家主页（MainActivity，底部 tab）
  ershoufang     → 二手房首页（SHHomePageActivity，通用列表）
  search_input   → 搜索输入（SearchHouseSuggestActivity）
  community_list → 小区房源列表（SecondHandHouseListActivity，搜索后）
"""
import logging
import subprocess
import time

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import WebDriverException

from easy_automation import StateMachine, get_context

logging.basicConfig(level=logging.INFO, format="%(name)s - %(message)s")
logger = logging.getLogger("lianjia")

PACKAGE = "com.homelink.android"
APPIUM_URL = "http://localhost:4723"

driver = None


# ============================================================
# Driver
# ============================================================
def create_driver():
    global driver
    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.automation_name = "UiAutomator2"
    options.no_reset = True
    options.set_capability("appium:skipDeviceInitialization", True)
    driver = webdriver.Remote(APPIUM_URL, options=options)
    driver.implicitly_wait(3)
    return driver


def d():
    global driver
    if driver is None:
        create_driver()
    return driver


def reconnect_driver():
    """UiAutomator2 server 崩溃时重建 session"""
    global driver
    if driver:
        try:
            driver.quit()
        except Exception:
            pass
        driver = None
    return create_driver()


# ============================================================
# Matchers — 顺序即优先级
# ============================================================
def is_login():
    return "login" in d().current_activity.lower()

def is_main_page():
    return d().current_activity in (".MainActivity", "com.homelink.android.MainActivity")

def is_search_input():
    return "SearchHouseSuggest" in d().current_activity

def is_community_list():
    """小区房源列表 — 搜索小区后进入"""
    return "SecondHandHouseList" in d().current_activity

def is_ershoufang():
    return "SHHomePage" in d().current_activity


# ============================================================
# Actions — 状态间转移
# ============================================================
def click_ershoufang_entry():
    """主页 → 二手房: 点击二手房入口"""
    d().find_element(AppiumBy.XPATH, '//*[@text="二手房"]').click()
    time.sleep(2)

def click_search_bar_home():
    """二手房首页 → 搜索: 点击搜索栏"""
    d().find_element(AppiumBy.ID, "com.homelink.android:id/fl_search_text_container").click()
    time.sleep(1)

def click_search_bar_community():
    """小区列表 → 搜索: 点击搜索栏"""
    d().find_element(AppiumBy.ID, "com.homelink.android:id/rl_search").click()
    time.sleep(1)

def search_and_select_community():
    """搜索 → 小区列表: 从 context 读小区名，输入并点击建议项"""
    name = get_context()["community"]
    inp = d().find_element(AppiumBy.ID, "com.homelink.android:id/et_search")
    inp.clear()
    time.sleep(0.5)
    inp.send_keys(name)
    time.sleep(2)

    suggestions = d().find_elements(AppiumBy.XPATH,
        f'//*[contains(@text, "{name}") '
        f'and not(@resource-id="com.homelink.android:id/et_search")]')
    if not suggestions:
        raise RuntimeError(f"搜索建议中未找到: {name}")
    suggestions[0].click()
    time.sleep(3)

def click_cancel_search():
    """搜索 → 返回上一页"""
    d().find_element(AppiumBy.XPATH, '//*[@text="取消"]').click()
    time.sleep(1)

def press_back():
    d().back()
    time.sleep(1)


# ============================================================
# Fallback — 杀 app 重启; 登录页直接报错
# ============================================================
def fallback():
    global driver
    try:
        if "login" in d().current_activity.lower():
            raise RuntimeError("检测到登录页，需人工登录后重新运行")
    except WebDriverException:
        pass

    logger.info("fallback: force-stop → 重启链家")
    subprocess.run(["adb", "shell", "am", "force-stop", PACKAGE])
    time.sleep(2)
    subprocess.run(["adb", "shell", "monkey", "-p", PACKAGE,
                     "-c", "android.intent.category.LAUNCHER", "1"],
                    capture_output=True)
    time.sleep(5)

    if driver:
        try:
            driver.quit()
        except Exception:
            pass
        driver = None
    create_driver()


# ============================================================
# 状态机图
# ============================================================
GRAPH = {
    "states": {
        "login":          {"matchers": ["is_login"]},
        "main_page":      {"matchers": ["is_main_page"]},
        "search_input":   {"matchers": ["is_search_input"]},
        "community_list": {"matchers": ["is_community_list"]},
        "ershoufang":     {"matchers": ["is_ershoufang"]},
    },
    "transitions": [
        {"from": "main_page",      "action": "click_ershoufang_entry",     "possible_targets": ["ershoufang"]},
        {"from": "ershoufang",     "action": "click_search_bar_home",      "possible_targets": ["search_input"]},
        {"from": "community_list", "action": "click_search_bar_community", "possible_targets": ["search_input"]},
        {"from": "search_input",   "action": "search_and_select_community", "possible_targets": ["community_list"]},
        {"from": "search_input",   "action": "click_cancel_search",        "possible_targets": ["ershoufang", "community_list"]},
        {"from": "community_list", "action": "press_back",                 "possible_targets": ["ershoufang", "search_input"]},
    ],
}

FUNCTIONS = {
    "is_login":                     is_login,
    "is_main_page":                 is_main_page,
    "is_search_input":              is_search_input,
    "is_community_list":            is_community_list,
    "is_ershoufang":                is_ershoufang,
    "click_ershoufang_entry":       click_ershoufang_entry,
    "click_search_bar_home":        click_search_bar_home,
    "click_search_bar_community":   click_search_bar_community,
    "search_and_select_community":  search_and_select_community,
    "click_cancel_search":          click_cancel_search,
    "press_back":                   press_back,
}


# ============================================================
# 业务逻辑 — goto 之间直接操作 Appium
# ============================================================
def sort_by_price_low_to_high():
    """点排序 → 总价从低到高"""
    try:
        d().find_element(AppiumBy.XPATH, '//*[@text="排序"]').click()
    except WebDriverException:
        reconnect_driver()
        d().find_element(AppiumBy.XPATH, '//*[@text="排序"]').click()
    time.sleep(1)
    d().find_element(AppiumBy.XPATH, '//*[contains(@text, "总价从低到高")]').click()
    time.sleep(2)


def scrape_top_prices(n: int = 10):
    """滚动收集前 n 套房源的总价(万)和单价(元/平)"""
    results = []
    seen_titles = set()  # 用标题去重（同价不同房）

    for scroll_round in range(8):
        try:
            infos = d().find_elements(AppiumBy.ID, "com.homelink.android:id/tv_house_info")
        except WebDriverException:
            reconnect_driver()
            infos = d().find_elements(AppiumBy.ID, "com.homelink.android:id/tv_house_info")
        prices = d().find_elements(AppiumBy.ID, "com.homelink.android:id/fl_price")

        for info_el, price_el in zip(infos, prices):
            title = info_el.text
            if title in seen_titles:
                continue
            seen_titles.add(title)

            # fl_price 子元素: [总价数字, "万", 单价]
            children = price_el.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView")
            total = children[0].text + "万" if children else "?"
            unit = children[2].text if len(children) > 2 else ""

            results.append({"info": title, "total": total, "unit": unit})
            if len(results) >= n:
                return results

        # 上滑加载更多
        size = d().get_window_size()
        d().swipe(size["width"] // 2, int(size["height"] * 0.7),
                  size["width"] // 2, int(size["height"] * 0.3), 800)
        time.sleep(1)

    return results


# ============================================================
# 主流程
# ============================================================
def main():
    communities = ["远东君悦庭", "城开珑庭"]
    all_results = {}

    create_driver()

    sm = StateMachine(GRAPH, functions=FUNCTIONS, context={})
    sm.set_fallback(fallback)
    sm.validate()

    for community in communities:
        logger.info(f"\n\n正在获取: {community}")

        # 设置目标小区，先到搜索页再搜索进入小区列表
        sm.context["community"] = community
        sm.goto("search_input")
        sm.goto("community_list")

        # 排序: 总价从低到高
        sort_by_price_low_to_high()

        # 抓取前10个价格
        prices = scrape_top_prices(10)
        all_results[community] = prices
        logger.info(f"{community}: 获取到 {len(prices)} 条")

    # 输出结果
    print("\n" + "=" * 60)
    print("最终结果")
    print("=" * 60)
    for community, prices in all_results.items():
        print(f"\n{community} — 最便宜的 {len(prices)} 套:")
        for i, item in enumerate(prices, 1):
            print(f"  {i}. {item['total']:>8s}  {item['unit']:>12s}  {item['info']}")

    driver.quit()


if __name__ == "__main__":
    main()
