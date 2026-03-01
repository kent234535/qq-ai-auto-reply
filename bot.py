import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBot11Adapter

nonebot.init(_env_file=".env")

driver = nonebot.get_driver()
driver.register_adapter(OneBot11Adapter)

nonebot.load_plugins("plugins")

# 挂载 Web 控制台（API + 静态文件）
from web import mount_web_app
mount_web_app(driver)

if __name__ == "__main__":
    nonebot.run()
