#该代码相较以前需要用户手动输入验证码（验证码图片会由默认图片查看器自动弹出）。
#Windows 用户：os.startfile(tmp_path) 会直接弹出图片查看器，很方便。此处做了适配。
#如果你是 Linux/Mac：改成 subprocess.call(['open', tmp_path]) (Mac)
#或 subprocess.call(['xdg-open', tmp_path]) (Linux)
#需要 import subprocess

#原作者的代码现在直接运行会报错，是因为现在大家使用的 Pillow（PIL 的现代 fork）版本是 10.0.0 或更高，从 Pillow 10.0.0 开始，Image.ANTIALIAS 这个常量被彻底移除（之前在 9.x 版本中已标记为弃用）。
#从 traceback 看，错误发生在验证码识别（OCR）过程中，脚本使用了 base64.b64decode 处理验证码图片，然后调用 OCR 的 classification 方法，使用了 ddddocr，而旧版本的 ddddocr 还在代码里硬编码了 Image.ANTIALIAS。
#此处删除了自动识别以防止不兼容问题再次发生。

import base64
import os
import tempfile
import html2text
import requests
from itertools import chain
from pprint import pprint
from io import BytesIO
from PIL import Image  # 用于打开和保存图片

Headers = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "SignCheck": "935465b771e207fd0f22f5c49ec70381",
    "TimeDate": "1694747726000",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/111.0.0.0 Safari/537.36",
}


def get_captcha() -> dict:
    """获取验证码信息"""
    captcha_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/98.0.4758.102 Safari/537.36",
    }
    captcha = requests.get(
        "https://centro.zjlll.net/ajax?&service=/centro/api/authcode/create&params=",
        headers=captcha_headers,
    ).json()["data"]
    return captcha


class ZJOOC:
    def __init__(self, username="", pwd=""):
        self.session = requests.Session()
        self.session.verify = False
        self._batch_dict = dict()
        self.login(username, pwd)
        self.coursemsg  # 触发一次获取课程信息

    def login(self, username="", pwd="") -> None:
        login_res: dict = {}
        while True:
            captcha_data = get_captcha()
            captcha_id = captcha_data["id"]

            # === 手动输入验证码部分开始 ===
            img_bytes = base64.b64decode(captcha_data["image"])
            img = Image.open(BytesIO(img_bytes))

            # 保存到临时文件并用系统默认程序打开图片（Windows 会自动弹出照片查看器）
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            img.save(tmp_file.name)
            tmp_path = tmp_file.name
            tmp_file.close()

            try:
                os.startfile(tmp_path)  # Windows 专用
            except AttributeError:
                # Linux / macOS 备用方式
                import subprocess
                if os.name == "posix":
                    if sys.platform == "darwin":  # macOS
                        subprocess.call(["open", tmp_path])
                    else:  # Linux
                        subprocess.call(["xdg-open", tmp_path])

            captcha_code = input("请查看弹出的验证码图片，输入验证码后按回车: ").strip()

            # 清理临时文件
            try:
                os.remove(tmp_path)
            except:
                pass
            # === 手动输入验证码部分结束 ===

            login_data = {
                "login_name": username,
                "password": pwd,
                "captchaCode": captcha_code,
                "captchaId": captcha_id,
                "redirect_url": "https://www.zjooc.cn",
                "app_key": "0f4cbab4-84ee-48c3-ba4c-874578754b29",
                "utoLoginTime": "7",
            }

            try:
                login_res = self.session.post(
                    "https://centro.zjlll.net/login/doLogin", data=login_data
                ).json()
            except Exception as ex:
                pprint(ex)
                print("登录请求异常，程序退出。")
                return

            if login_res.get("resultCode", 1) == 0:
                print("验证码正确，登录成功！")
                break
            else:
                print("验证码错误或账号密码有误，正在重新获取验证码...")
                continue

        # 第二次跳转完成自动登录
        login_param = {
            "auth_code": login_res.get("authorization_code", ""),
            "autoLoginTime": "7",
        }
        self.session.get("https://www.zjooc.cn/autoLogin", params=login_param)
        print("Login success.")

    @property
    def infomsg(self) -> dict:
        params = {"service": "/centro/api/user/getProfile", "params[withDetail]": True}
        info_data = self.session.get(
            "https://www.zjooc.cn/ajax", params=params, headers=Headers
        ).json()["data"]

        course_msg_dict = {
            "name": info_data["name"],
            "corpName": info_data["corpName"],
            "studentNo": info_data["studentNo"],
            "loginName": info_data["loginName"],
            "roleType": info_data["roleType"],
        }
        return course_msg_dict

    @property
    def coursemsg(self) -> list:
        params = {
            "service": "/jxxt/api/course/courseStudent/student/course",
            "params[pageNo]": 1,
            "params[pageSize]": 5,
            "params[coursePublished]=": "",
            "params[courseName]": "",
            "params[batchKey]": "",
        }
        course_msg_data = self.session.get(
            "https://www.zjooc.cn/ajax",
            params=params,
            headers=Headers,
        ).json()["data"]
        course_lst = [
            {
                "id": i,
                "courseId": course_msg_data[i]["id"],
                "courseName": course_msg_data[i]["name"],
                "courseBatchId": course_msg_data[i]["batchId"],
                "courseProcessStatus": course_msg_data[i]["processStatus"],
            }
            for i in range(len(course_msg_data))
        ]

        self._batch_dict = {
            course_msg_data[i]["id"]: course_msg_data[i]["batchId"]
            for i in range(len(course_msg_data))
        }

        return course_lst

    def _get_msg(self, modes: str | int) -> list:
        modes = str(modes)
        msg_lst: list = []
        for mode in modes:
            params = {
                "params[pageNo]": 1,
                "params[pageSize]": 20,
                "params[paperType]": mode,
                "params[batchKey]": 20231,
            }

            res_msg_data = self.session.get(
                "https://www.zjooc.cn/ajax?service=/tkksxt/api/admin/paper/student/page",
                params=params,
                headers=Headers,
            ).json()["data"]

            msg_lst.extend(
                [
                    {
                        "id": idx,
                        "courseName": data["courseName"],
                        "paperName": data["paperName"],
                        "classId": data["classId"],
                        "courseId": data["courseId"],
                        "paperId": data["paperId"],
                        "scorePropor": data["scorePropor"],
                    }
                    for idx, data in enumerate(res_msg_data)
                ]
            )

        if not msg_lst:
            print("🤣🤣🤣  Congrats!! all work you have done!!!")
        return msg_lst

    @property
    def quizemsg(self) -> list:
        return self._get_msg("0")

    @property
    def exammsg(self) -> list:
        return self._get_msg("1")

    @property
    def hwmsg(self) -> list:
        return self._get_msg("2")

    @property
    def scoremsg(self) -> list:
        score_lst = []
        params = {
            "service": "/report/api/course/courseStudentScore/scoreList",
            "params": {
                "pageNo": 1,
                "pageSize": 20,
                "courseId": "",
                "batchKey": "",
            },
            "checkTimeout": "true",
        }

        res_score_data = self.session.get(
            "https://www.zjooc.cn/ajax?",
            params=params,
            headers=Headers,
        ).json()["data"]
        score_lst = [
            {
                "courseId": data["courseId"],
                "courseName": data["courseName"],
                "finalScore": data["finalScore"],
                "videoScore": data["videoScore"],
                "onlineScore": data["onlineScore"],
                "offlineScore": data["offlineScore"],
                "testScore": data["testScore"],
                "homeworkScore": data["homeworkScore"],
            }
            for data in res_score_data
        ]

        return score_lst

    def get_video_msg(self, course_id) -> list:
        params = {
            "params[pageNo]": 1,
            "params[courseId]": course_id,
            "params[urlNeed]": "0",
        }
        video_data = self.session.get(
            "https://www.zjooc.cn/ajax?service=/jxxt/api/course/courseStudent/getStudentCourseChapters",
            params=params,
            headers=Headers,
        ).json()["data"]
        video_msg = [
            {
                "Name": f'{chapter["name"]}-{section["name"]}-{resource["name"]}',
                "courseId": course_id,
                "chapterId": resource["id"],
                "time": resource.get("vedioTimeLength", 0),
            }
            for chapter in video_data
            for section in chapter["children"]
            for resource in section["children"]
            if resource["learnStatus"] == 0
        ]

        return video_msg

    def do_video(self, course_id):
        if not course_id:
            return

        video_lst = self.get_video_msg(course_id=course_id)
        video_cnt = len(video_lst)

        for idx, video in enumerate(video_lst, start=1):
            if video["time"]:
                params = {
                    "params[chapterId]": video["chapterId"],
                    "params[courseId]": video["courseId"],
                    "params[playTime]": str(video["time"]),
                    "params[percent]": "100",
                }

                self.session.get(
                    "https://www.zjooc.cn/ajax?service=/learningmonitor/api/learning/monitor/videoPlaying",
                    params=params,
                    headers=Headers,
                ).json()
            else:
                params = {
                    "params[courseId]=": video["courseId"],
                    "params[chapterId]=": video["chapterId"],
                }
                self.session.get(
                    "https://www.zjooc.cn/ajax?service=/learningmonitor/api/learning/monitor/finishTextChapter",
                    params=params,
                    headers=Headers,
                ).json()
            progress = idx / video_cnt
            print(
                "\r",
                video["Name"] + " is doing！" + "\r",
                "😎" * int(progress * 10) + ".." * (10 - int(progress * 10)),
                f"[{progress:.0%}]",
                end="",
            )
        print("\nall video done!")

    def get_an(self, paperId, course_id) -> dict:
        if not all([paperId, course_id]):
            return {}

        res_answer_data: list = []
        try:
            answer_data = {
                "service": "/tkksxt/api/student/score/scoreDetail",
                "body": "true",
                "params[batchKey]": self._batch_dict.get(course_id, 20231),
                "params[paperId]": paperId,
                "params[courseId]": course_id,
            }

            res_answer_data = self.session.post(
                "https://www.zjooc.cn/ajax",
                data=answer_data,
                headers=Headers,
            ).json()["data"]["paperSubjectList"]
        except Exception as ex:
            print("err:", ex)

        pprint(
            {
                html2text.html2text(an_data["subjectName"]): html2text.html2text(
                    an_data["subjectOptions"][ord(an_data["rightAnswer"]) - 65][
                        "optionContent"
                    ]
                )
                for an_data in res_answer_data
            }
        )
        return {an_data["id"]: an_data["rightAnswer"] for an_data in res_answer_data}

    def do_an(self, paper_id, course_id, class_id):
        if not all([paper_id, course_id, class_id]):
            return

        paper_an_data = self.get_an(paper_id, course_id)
        answesparams = {
            "service": "/tkksxt/api/admin/paper/getPaperInfo",
            "params[paperId]": paper_id,
            "params[courseId]": course_id,
            "params[classId]": class_id,
            "params[batchKey]": self._batch_dict.get(course_id),
        }
        paper_data = self.session.get(
            "https://www.zjooc.cn/ajax",
            params=answesparams,
            headers=Headers,
        ).json()["data"]

        send_data = {
            "service": "/tkksxt/api/student/score/sendSubmitAnswer",
            "body": "true",
            "params[batchKey]": self._batch_dict.get(course_id),
            "params[id]": paper_data["id"],
            "params[stuId]": paper_data["stuId"],
            "params[clazzId]": paper_data["paperSubjectList"],
            "params[scoreId]": paper_data["scoreId"],
            **{
                f"params[paperSubjectList][{idx}][{k}]": v
                for idx, subject in enumerate(paper_data["paperSubjectList"])
                for k, v in {
                    "id": subject["id"],
                    "subjectType": subject["subjectType"],
                    "answer": paper_an_data.get(subject["id"], ""),
                }.items()
            },
        }
        try:
            res = self.session.post(
                "https://www.zjooc.cn/ajax", data=send_data, headers=Headers
            )
            res.raise_for_status()
            print("提交答案成功")
        except requests.RequestException as e:
            print("Failed to send data!!", e)

    def do_ans(self):
        messages_lst = [self.exammsg, self.hwmsg, self.quizemsg]
        paper_cnt = sum(len(msg) for msg in messages_lst)
        for idx, msg in enumerate(chain(*messages_lst)):
            if msg["scorePropor"] != "100/100.0":
                self.do_an(
                    paper_id=msg["paperId"],
                    course_id=msg["courseId"],
                    class_id=msg["classId"],
                )
                progress = (idx + 1) / paper_cnt
                progress_bar = f"{'😎' * int(progress * 10)}{'--' * (10 - int(progress * 10))}[{progress:.0%}]"
                print("\r", progress_bar, end="")
        print("\nAll done!")

    def paser(self, commands: str):
        command_list = commands.split()

        def error_msg():
            print("paser err!!!")
            print("please enter your commands again!")

        try:
            match command_list[0]:
                case "msg":
                    match command_list[1]:
                        case "0" | "1" | "2":
                            pprint(self._get_msg(command_list[1]))
                        case "3":
                            pprint(self.infomsg)
                        case "4":
                            pprint(self.coursemsg)
                        case "5":
                            pprint(self.scoremsg)
                        case "6":
                            if len(command_list) < 3:
                                error_msg()
                            else:
                                pprint(self.get_video_msg(command_list[2]))
                        case "7":
                            if len(command_list) < 4:
                                error_msg()
                            else:
                                self.get_an(command_list[2], command_list[3])
                        case _:
                            error_msg()
                case "do":
                    match command_list[1]:
                        case "0":
                            if len(command_list) < 5:
                                error_msg()
                            else:
                                self.do_an(
                                    paper_id=command_list[2],
                                    course_id=command_list[3],
                                    class_id=command_list[4],
                                )
                        case "1":
                            if len(command_list) < 3:
                                error_msg()
                            else:
                                self.do_video(command_list[2])
                        case "2":
                            self.do_ans()
                        case _:
                            error_msg()
                case _:
                    error_msg()
        except Exception as ex:
            error_msg()
            print(ex)
