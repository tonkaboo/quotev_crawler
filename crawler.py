from urllib import request, parse
from bs4 import BeautifulSoup
import re
import argparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
import time

# 爬取给定url的页面
def get_html(url):
    with open('./log.txt', 'a', encoding='utf-8') as file:
        file.write(f'正在准备爬取{url}\n')
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36"}
    # 书名可能包含non-ASCII字符，因此需要quote一下
    quoted_url = parse.quote(url, safe=':/?=')
    req = request.Request(url=quoted_url, headers=headers)
    response = request.urlopen(req)
    html = response.read()
    request.urlcleanup()
    return html

# 从html页面中解析出文本内容
# 若需要获取之后的章节内容，请把is_first_chapter置真
# 若需要存储这一章的文本内容，请把save_as_text置真
def get_chapter(url, is_first_chapter=False, save=True):
    html = get_html(url)
    # 使用bs4解析页面
    soup = BeautifulSoup(html, "html.parser")
    title = soup.select("div#quizHeaderTitle > h1")[0].get_text()
    title = '-'.join(re.findall('\w+', title))
    paragraphs = soup.select("#rescontent > p")

    # 获得所有包含文本的段落后，对这些段落进行处理
    story = ''
    for paragraph in paragraphs:
        story += paragraph.get_text() + '\n'
    print(story)

    if save:
        save_as_txt(story, title)

    # 若有需要，可以获取全文
    if is_first_chapter:
        print(title)
        get_all_chapters(soup)

# 将爬取的文章保存成txt格式
def save_as_txt(story, title):
    with open(f'./fanfics/{title}.txt', 'a', encoding='utf-8') as file:
        file.write(story)

# 由首章获取所有章节
def get_all_chapters(soup):
    index = soup.find("select", {"name":"rid"})
    # 若未找到索引（即只有一章），则直接返回
    if index == None:
        return
    # 如果找到了索引，要找到包括书名的url
    base_url = re.findall('https://www.quotev.com/story/\d+/[^/]+/', index["onchange"])[0]
    # 书名可能包含non-ASCII字符，因此需要quote一下
    quoted_base_url = parse.quote(base_url, safe=':/')
    
    # 找到最后一章，生成所有章节的url
    chapters = index.find_all('option')
    for chapter in chapters[1:]:
        chapter_url = quoted_base_url + str(chapter['value'])
        get_chapter(chapter_url)  

# 由太太的首页信息获取她全部作品的url                            
def get_works_url(author_page_url, works, page=1, is_first_page=False):
    published_works_page = author_page_url + '/published?page=' + str(page)
    html = get_html(published_works_page)
    soup = BeautifulSoup(html, "html.parser")

    # 排一下雷
    is_minefield = caution(soup)
    if is_minefield:
        return
    
    works_nodes = soup.select(".innerquiz .image a")
    for node in works_nodes:
        works.append(node["href"])

    # 若当前页面并非第1页，直接返回即可（可能是递归到这儿了）
    if is_first_page == False:
        return

    # 即使是第1页，也有可能这个太太本身的作品就只有一页
    last_page_wrapper = soup.select('ul.nosel select option')
    if last_page_wrapper == []:
        return
    last_page = last_page_wrapper[-1].get_text()
    i = 1
    while i < int(last_page):
        i += 1
        get_works_url(author_page_url, works, page=i)

# 获取太太的全部作品
def get_works(author_page_url):
    works_list = []
    get_works_url(author_page_url, works_list, page=1, is_first_page=True)
    for url in works_list:
        get_chapter(url, is_first_chapter=True)
    # 获取完毕全部作品后，将这位太太加入已爬取的列表
    with open('./listed_authors.txt', 'a', encoding='utf-8') as file:
        file.write(author_page_url+'\n')

# 获取用户user_id的关注/粉丝（类别由type指明）
def get_connections(user_id, type):
    allowed_types = ['following', 'followers']
    if type not in allowed_types:
        raise ValueError(f'Invalid value for param: {type}. Allowed values are {allowed_types}')
    url = f'https://www.quotev.com/{user_id}/{type}'

    connections = []

    chrome_options = Options()
    chrome_options.add_argument('--disable-gpu')
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    while True:
        before_scroll = len(driver.find_elements_by_css_selector('.rtlAlign'))
        # 模拟滚动到页面底部的操作
        driver.find_element_by_tag_name('body').send_keys(Keys.END)
        # 等待页面加载
        time.sleep(3)
        after_scroll = len(driver.find_elements_by_css_selector('.rtlAlign'))
        if after_scroll == before_scroll:
            break
    connection_elements = driver.find_elements_by_css_selector('.rtlAlign > a')
    for element in connection_elements:
        href = element.get_attribute('href')
        connections.append(href)
    driver.close()
    
    return connections

# 获取某用户关注的所有太太的作品
def get_following(user_id):
    followings = get_connections(user_id, 'following')
    listed_authors = set()
    with open('./listed_authors.txt', 'r', encoding='utf-8') as file:
        for line in file.readlines():
            listed_authors.add(line.strip())

    for following in followings:
        if following in listed_authors:
            continue
        else:
            get_works(following)

# 获取太太的所有粉丝关注的其他太太的作品
def get_followers(user_id):
    followers_url = get_connections(user_id, 'followers')
    followers_url = followers_url
    for follower_url in followers_url:
        follower_id = parse.urlparse(follower_url).path[1:]
        get_following(follower_id)

# 避雷！
def caution(soup, keywords=['博君一肖', 'bjyx', '肖战', '王一博']):
    text = soup.get_text()
    for keyword in keywords:
        if keyword in text:
            print('雷！')
            return True # 有雷，快跑！
    return False

def id_to_url(id, type):
    switcher = {
        'story': f'https://www.quotev.com/story/{id}',
        'user_works': f'https://www.quotev.com/{id}/published',
        'user_following': f'https://www.quotev.com/{id}/following',
        'user_followers': f'https://www.quotev.com/{id}/followers'
    }
    return switcher[type]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--story', help='文章[id]，获取该文章')
    parser.add_argument('--author', help='用户[id/昵称]，获取该用户的所有作品')
    parser.add_argument('--save', help='将爬取的文章存储至本地', action='store_true')
    connection_group = parser.add_mutually_exclusive_group()
    connection_group.add_argument('--following', help='用户[id/昵称]，获取该用户关注的所有用户的作品')
    connection_group.add_argument('--connections', help='用户[id/昵称]，获取与该用户有社交关系（关注&粉丝）的所有用户的作品')
    args = parser.parse_args()

    save_flag = args.save
        
    if args.story:
        url = id_to_url(args.story, 'story')
        get_chapter(url, is_first_chapter=True, save=save_flag)
    
    if args.author:
        url = id_to_url(args.author, 'user_works')
        get_works(url)

    if args.following:
        get_following(args.following)
    elif args.connections:
        get_following(args.connections)
        try:
            get_followers(args.connections)
        except ValueError as e:
            print(e)


if __name__ == "__main__":
    main()