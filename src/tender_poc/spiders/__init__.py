from tender_poc.spiders.cec import CecSpider
from tender_poc.spiders.chnenergy import ChnEnergySpider
from tender_poc.spiders.crrc import CrrcSpider
from tender_poc.spiders.ggzy import GgzySpider
from tender_poc.spiders.sdic import SdicSpider


SPIDERS = {
    "cec": CecSpider,
    "chnenergy": ChnEnergySpider,
    "crrc": CrrcSpider,
    "ggzy": GgzySpider,
    "sdic": SdicSpider,
}

__all__ = ["SPIDERS", "CecSpider", "ChnEnergySpider", "CrrcSpider", "GgzySpider", "SdicSpider"]
