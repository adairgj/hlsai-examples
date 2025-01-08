from dataclasses import dataclass

@dataclass
class Consts:
    ApiVersion: str
    ApiEndpoint: str
    AzureResourceManager: str
    AccountName: str
    ResourceGroup: str
    SubscriptionId: str

    def __post_init__(self):
        if not self.SubscriptionId or not self.AccountName or not self.ResourceGroup:
            raise ValueError('Please Fill In SubscriptionId, Account Name and Resource Group on the Constant Class!')
