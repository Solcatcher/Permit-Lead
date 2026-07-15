from connectors.tampa_city import TampaCityConnector
from connectors.hillsborough_county import HillsboroughCountyConnector
from connectors.hillsborough_dev_review import HillsboroughDevReviewConnector
from connectors.lakeland import LakelandConnector
from connectors.hernando_county import HernandoCountyConnector
from connectors.pinellas_drs import PinellasDRSConnector
from connectors.pasco_county import PascoCountyConnector

ALL_CONNECTORS = {
    "tampa_city": TampaCityConnector,
    "hillsborough_county": HillsboroughCountyConnector,
    "hillsborough_dev_review": HillsboroughDevReviewConnector,
    "lakeland": LakelandConnector,
    "hernando_county": HernandoCountyConnector,
    "pinellas_drs": PinellasDRSConnector,
    "pasco_county": PascoCountyConnector,
}
