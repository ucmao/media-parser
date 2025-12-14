import json
import urllib3
import warnings
import copy
import requests
from utils.web_fetcher import UrlParser
from utils.douyin_utils.bogus_sign_utils import CommonUtils
from configs.logging_config import logger
from src.downloaders.base_downloader import BaseDownloader

warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)


class DouyinDownloader(BaseDownloader):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.common_utils = CommonUtils()
        self.headers = {
            'sec-ch-ua': '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
            'Accept': 'application/json, text/plain, */*',
            'sec-ch-ua-mobile': '?0',
            'User-Agent': self.common_utils.user_agent,
            'sec-ch-ua-platform': '"Windows"',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        self.ms_token = self.common_utils.get_ms_token()
        self.ttwid = '1%7CvDWCB8tYdKPbdOlqwNTkDPhizBaV9i91KjYLKJbqurg%7C1723536402%7C314e63000decb79f46b8ff255560b29f4d8c57352dad465b41977db4830b4c7e'
        self.webid = '7307457174287205926'
        self.fetch_html_content()
        self.aweme_id = UrlParser.get_video_id(self.real_url)
        self.data = self.fetch_html_data()

    def fetch_html_data(self):
        referer_url = f"https://www.douyin.com/video/{self.aweme_id}?previous_page=web_code_link"
        play_url = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?device_platform=webapp&aid=6383&channel=channel_pc_web&aweme_id={self.aweme_id}&update_version_code=170400&pc_client_type=1&version_code=190500&version_name=19.5.0&cookie_enabled=true&screen_width=1536&screen_height=864&browser_language=zh-CN&browser_platform=Win32&browser_name=Chrome&browser_version=127.0.0.0&browser_online=true&engine_name=Blink&engine_version=127.0.0.0&os_name=Windows&os_version=10&cpu_core_num=8&device_memory=8&platform=PC&downlink=1.25&effective_type=4g&round_trip_time=50&webid={self.webid}&msToken={self.ms_token}"
        new_headers = copy.deepcopy(self.headers)
        new_headers['Referer'] = referer_url
        new_headers['Cookie'] = f"ttwid={self.ttwid}; UIFID_TEMP=973a3fd64dcc46a3490fd9b60d4a8e663b34df4ccc4bbcf97643172fb712d8b085a6744acabbffda742bf60a364e4bd6ba5522889cc6f6598b4ea0b83bec2c70bac5163dec36cdb8fb58ea1ae00a413d; s_v_web_id=verify_lzhq5z5k_lbhbXlzb_o9V2_4SQt_8VKz_WZhdN8ARwLk5; home_can_add_dy_2_desktop=%220%22; dy_swidth=1536; dy_sheight=864; stream_recommend_feed_params=%22%7B%5C%22cookie_enabled%5C%22%3Atrue%2C%5C%22screen_width%5C%22%3A1536%2C%5C%22screen_height%5C%22%3A864%2C%5C%22browser_online%5C%22%3Atrue%2C%5C%22cpu_core_num%5C%22%3A8%2C%5C%22device_memory%5C%22%3A8%2C%5C%22downlink%5C%22%3A10%2C%5C%22effective_type%5C%22%3A%5C%224g%5C%22%2C%5C%22round_trip_time%5C%22%3A50%7D%22; csrf_session_id=c25ac0fd3e72f260d4d666d4e5b59401; strategyABtestKey=%221722906710.493%22; passport_csrf_token=e8e0d86abdd80d40b0a35f4417140777; passport_csrf_token_default=e8e0d86abdd80d40b0a35f4417140777; bd_ticket_guard_client_web_domain=2; FORCE_LOGIN=%7B%22videoConsumedRemainSeconds%22%3A180%7D; fpk1=U2FsdGVkX1/MzFW4T42Rh27SkY1k9enxmP1563AOYXnpFPaQOzdqmDBHwkaQrfKGx2e0KwNeDci6fNn3aTjflw==; fpk2=362d7fe3d8b2581bffa359f0eeda7106; UIFID=973a3fd64dcc46a3490fd9b60d4a8e663b34df4ccc4bbcf97643172fb712d8b0001661437e34e9c40cd654256ca161ee16bfeed98d4c55748714f5d5e8b3961f299814cae48bfbbd1b49196b4ee347af48639652b3235c20ab5ceedde56f53b486cfba7e3400cb7f7d39bc7dbade81d368864fde51e4c52065bf7329ca6a7be919aa4b6add8afe59f8857a5fccb62199c9e66654824ef007ff13d9780400ad16; volume_info=%7B%22isUserMute%22%3Afalse%2C%22isMute%22%3Atrue%2C%22volume%22%3A0.5%7D; biz_trace_id=d2dfa5cf; bd_ticket_guard_client_data=eyJiZC10aWNrZXQtZ3VhcmQtdmVyc2lvbiI6MiwiYmQtdGlja2V0LWd1YXJkLWl0ZXJhdGlvbi12ZXJzaW9uIjoxLCJiZC10aWNrZXQtZ3VhcmQtcmVlLXB1YmxpYy1rZXkiOiJCR1ZlY2RTY2piNWVBcHc0aVNTaTFrTThYSXdDOHNaK0NoSk16WWpyc2ZyWEYvT3VmMTB3MGpZMWpLZXdQWTFLQ0xLeERzajE5V3Y4RXlKc1U2MzlKejQ9IiwiYmQtdGlja2V0LWd1YXJkLXdlYi12ZXJzaW9uIjoxfQ%3D%3D; download_guide=%221%2F20240806%2F0%22; IsDouyinActive=false; __ac_nonce=066b1804600a583d1df8e; __ac_signature=_02B4Z6wo00f01b-.zKAAAIDA3JBBKKMofAG.n8gAAAlf52; __ac_referer={referer_url}"
        abogus = self.common_utils.get_abogus(play_url, self.common_utils.user_agent)
        url = f"{play_url}&a_bogus={abogus}"
        response = requests.get(url, headers=new_headers, verify=False, timeout=3)
        if response.text:
            return response.json()
        else:
            logger.warning(f"获取视频标题地址封面图失败")
            return None

    def get_real_video_url(self):
        try:
            data_dict = self.data
            play_addr_list = data_dict['aweme_detail']['video']['bit_rate'][0]['play_addr']['url_list']
            # play_addr_list[0]:主CDN节点; play_addr_list[1]:备用CDN节点; play_addr_list[2]:抖音官方的源站URL
            play_addr = play_addr_list[2]
            return play_addr
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse video URL: {e}")

    def get_title_content(self):
        try:
            data_dict = self.data
            title_content = data_dict['aweme_detail']['desc']
            return title_content
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse title content: {e}")

    def get_cover_photo_url(self):
        try:
            data_dict = self.data
            play_cover = data_dict['aweme_detail']['video']['cover_original_scale']['url_list'][0]
            return play_cover
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse cover URL: {e}")


if __name__ == '__main__':
    real_url = 'https://www.douyin.com/video/7396822576074460467'
    dl = DouyinDownloader(real_url)
    print(dl.get_title_content())
    print(dl.get_cover_photo_url())
    print(dl.get_real_video_url())
