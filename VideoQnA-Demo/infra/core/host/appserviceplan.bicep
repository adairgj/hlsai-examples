param name string
param appServicePlanLocation string
param tags object = {}

param kind string = 'linux'
param reserved bool = true
param sku object

resource appServicePlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: name
  location: appServicePlanLocation
  tags: tags
  sku: sku
  kind: kind
  properties: {
    reserved: reserved
  }
}

output id string = appServicePlan.id
output name string = appServicePlan.name
