import requests
import json
import time
from rich.table import Table
from rich.console import Console
from rich import box
from rich.live import Live
import datetime
from datetime import timedelta
import dingding
import feishu

headers = {
    'Content-Type': 'application/json',
    'Request-Source': 'PC',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6)'
                  ' AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'
}

# 排除的日期
exclude_date = []

def parsing_url(url: str):
    """
    解析所需解析门诊地址，强制要求满足格式

    https://www.114yygh.com/hospital/162/10c186f26ae7ecf8160e2dcf1f2e7312/200053566/source
    {"hosCode": url_split[4], "firstDeptCode": url_split[5], "secondDeptCode": url_split[6]}

    :param url: 门诊地址
    :return:
    """

    url_split = url.split("/")
    if len(url_split) != 8:
        return None
    else:
        md = {}
        headers["Referer"] = url

        hos_code = url_split[4]
        first_dept_code = url_split[5]
        second_dept_code = url_split[6]

        week_os_info = request_week_os_info(first_dept_code, second_dept_code, hos_code)
        if week_os_info is not None:
            md.update(week_os_info)

        os_base_properties = request_os_properties(first_dept_code, second_dept_code, hos_code)
        if os_base_properties is not None:
            md.update(os_base_properties)

        md["search_url"] = url

        return md


def request_week_os_info(first_dept_code: str, second_dept_code: str, hos_code: str):
    """
    获取当前一星期的预约状况

    :param first_dept_code: first_dept_code
    :param second_dept_code: second_dept_code
    :param hos_code: hos_code
    :return:
    """

    body = {
        "firstDeptCode": first_dept_code,
        "secondDeptCode": second_dept_code,
        "hosCode": hos_code,
        "week": 1
    }

    request_url = "https://www.114yygh.com/web/product/list"

    response_data = None
    while True:
        try:
            response_data = requests.post(request_url, headers=headers, data=json.dumps(body))
            break
        except Exception as e:
            print(f"request_week_os_info function response_data caught exception: {e}")
            time.sleep(5)

    response = None
    if response_data is not None:
        try:
            response = response_data.json()
        except Exception as e:
            print(f"request_week_os_info function response caught exception: {e}")
            return None

    if response is None or response["resCode"] != 0:
        return None

    return response["data"]


def request_os_properties(first_dept_code: str, second_dept_code: str, hos_code: str):
    """
    通过请求地址获取门诊信息

    :param first_dept_code: first_dept_code
    :param second_dept_code: second_dept_code
    :param hos_code: hos_code
    :return:
    """

    format_url = "https://www.114yygh.com/web/department/hos/detail?firstDeptCode={}&secondDeptCode={}&hosCode={}"

    request_url = format_url.format(first_dept_code, second_dept_code, hos_code)

    response_data = None
    while True:
        try:
            response_data = requests.get(request_url, headers=headers)
            break
        except Exception as e:
            print(f"request_os_properties function response_data caught exception: {e}")
            time.sleep(5)

    response = None
    if response_data is not None:
        try:
            response = response_data.json()
        except Exception:
            return None

    if response is None or response["resCode"] != 0:
        return None

    return response["data"]


def parsing_url_with_list(urls: list) -> list:
    """
    将多个门诊地址进行解析并返回

    :param urls: 门诊集合列表
    :return:
    """

    os_parsed_list = []
    for curl in urls:
        data = parsing_url(curl)
        if data is not None:
            os_parsed_list.append(data)

    return os_parsed_list


def all_info_of_table(request_os_list: list) -> Table:
    parsed_data = parsing_url_with_list(request_os_list)

    # 最近一周的日期 %Y-%m-%d
    week_of_name = []
    now = datetime.datetime.now()
    week_of_name.append(now.strftime("%Y-%m-%d"))
    for value in range(1, 7):
        next_day = now + timedelta(days=value)
        week_of_name.append(next_day.strftime("%Y-%m-%d"))

    table = Table(box=box.ROUNDED, title="[aquamarine3]114 网上预约实时监控({})".format(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))))

    table.add_column('[light_sea_green]医院', justify="center")
    table.add_column('[light_sea_green]科部', justify="center")
    table.add_column('[light_sea_green]门诊', justify="center")

    for value in week_of_name:
        table.add_column('[light_sea_green]' + value, justify="center")

    available = []

    for data in parsed_data:

        week_of_dict = {0: "[red]未知", 1: "[red]未知", 2: "[red]未知", 3: "[red]未知", 4: "[red]未知", 5: "[red]未知",
                        6: "[red]未知"}

        hospital_dict = {"hosName": data.get("hosName", "未知"),
                         "firstDeptName": data.get("firstDeptName", "未知"),
                         "secondDeptName": data.get("secondDeptName", "未知")}

        # 核心数据为空则跳过
        cal_exists = data.get("calendars")
        if cal_exists is None:
            continue

        yuyue_available = []
        for index, value in enumerate(week_of_name):
            for calendars in data["calendars"]:
                if value == calendars["dutyDate"]:
                    if calendars["status"] == "NO_INVENTORY":
                        # 无号
                        week_of_dict[index] = "[red3]无号"
                    elif calendars["status"] == "AVAILABLE":
                        # 可约
                        week_of_dict[index] = "[green]可预约"

                        vc = [value, "可预约"]
                        if value not in exclude_date:
                            yuyue_available.append(" | " + ' | '.join(vc) + " |\n")
                    elif calendars["status"] == "SOLD_OUT":
                        # 约满
                        week_of_dict[index] = "[indian_red]已约满"
                    elif calendars["status"] == "TOMORROW_OPEN":
                        # 即将放号
                        week_of_dict[index] = "[steel_blue1]即将放号"
                    else:
                        week_of_dict[index] = "[red]未知状态"
                    break

        hospital_dict["yuyue"] = yuyue_available
        hospital_dict["search_url"] = data.get("search_url", "未知")
        available.append(hospital_dict)
        table.add_row(data.get("hosName", "未知"), data.get("firstDeptName", "未知"), data.get("secondDeptName", "未知"),
                      week_of_dict[0], week_of_dict[1],
                      week_of_dict[2], week_of_dict[3],
                      week_of_dict[4], week_of_dict[5],
                      week_of_dict[6])

    # dingding.send(available)
    feishu.send(available)
    return table


if __name__ == '__main__':
    console = Console(color_system='256', style=None)

    cookie = console.input(":surfer:[bold deep_sky_blue3] 请输入114北京市预约挂号统一平台授权凭证Cookie：\n")
    headers["Cookie"] = cookie

    exclude = console.input(":surfer:[bold deep_sky_blue3] 请输入排除的日期，多个通过[,]分隔。(2022-12-12,2022-12-13)：\n")
    exclude_date = exclude.split(",")

    os_list = []

    url = console.input(":robot:[bold sky_blue2] 请键入要实时查询的门诊地址：\n")
    os_list.append(url)

    while True:
        access_or_url = console.input(":heavy_exclamation_mark:[bold red1] 键入[Y]进行查询，否则继续批量录入门诊URL：\n")
        if access_or_url == "Y":
            break
        else:
            os_list.append(access_or_url)

    os_data = None
    with console.status("[light_goldenrod3]正在首次加载数据...[/]", spinner="moon"):
        os_data = all_info_of_table(os_list)

    # 首次加载由外部完成，normal为正常加载sleep 5s
    normal = False
    with Live(console=console, screen=True, auto_refresh=False) as live:
        while True:
            if normal:
                time.sleep(30)
                os_data = all_info_of_table(os_list)

            live.update(os_data, refresh=True)
            normal = True
