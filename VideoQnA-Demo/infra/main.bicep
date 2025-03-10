targetScope = 'resourceGroup'

@minLength(1)
@maxLength(64)
@description('Name of the environment which is used to generate a short unique hash used in all resources.')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Location for the App Service Plan')
param appServicePlanLocation string

@description('Location for the App Services')
param appServicesLocation string

param appServicePlanName string = ''
param backendServiceName string = ''

param searchServiceName string = 'hlsvideosearch'
param searchIndexName string = 'prompt-content-indexdb'

param openAiServiceName string = 'videosearch-openai'
param openAiResourceGroupName string = 'rg-training-video-search-engine'

param chatGptDeploymentName string = 'gpt-4o'
param embeddingsDeploymentName string = 'text-embedding-ada-002'
param azureOpenaiApiKey string = ''
param azureSearchKey string = ''

param promptContentDbName string = ''
param promptContentDb string = ''
param languageModel string = ''

@description('Id of the user or app to assign application roles')
param principalId string = ''

var abbrs = loadJsonContent('abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = { 'azd-env-name': environmentName }

// Create an App Service Plan to group applications under the same payment plan and SKU
module appServicePlan 'core/host/appserviceplan.bicep' = {
  name: 'appserviceplan'
  params: {
    name: !empty(appServicePlanName) ? appServicePlanName : '${abbrs.webServerFarms}${resourceToken}'
    appServicePlanLocation: appServicePlanLocation
    tags: tags
    sku: {
      name: 'B1'
      tier: 'Basic'
      size: 'B1'
      family: 'B'
      capacity: 1
    }
    kind: 'linux'
  }
}

// The application backend
module backend 'core/host/appservice.bicep' = {
  name: 'web'
  params: {
    name: !empty(backendServiceName) ? backendServiceName : '${abbrs.webSitesAppService}backend-${resourceToken}'
    appServicesLocation: appServicesLocation
    tags: union(tags, { 'azd-service-name': 'backend' })
    appServicePlanId: appServicePlan.outputs.id
    runtimeName: 'python'
    runtimeVersion: '3.10'
    scmDoBuildDuringDeployment: true
    managedIdentity: true
    appSettings: {
      AZURE_OPENAI_SERVICE: openAiServiceName
      AZURE_SEARCH_INDEX: searchIndexName
      AZURE_SEARCH_SERVICE: searchServiceName
      AZURE_OPENAI_CHATGPT_DEPLOYMENT: chatGptDeploymentName
      AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT: embeddingsDeploymentName
      AZURE_OPENAI_API_KEY: azureOpenaiApiKey
      AZURE_SEARCH_KEY: azureSearchKey
      PROMPT_CONTENT_DB_NAME: promptContentDbName
      PROMPT_CONTENT_DB: promptContentDb
      LANGUAGE_MODEL: languageModel
    }
  }
}


module searchRoleUser 'core/security/role.bicep' = {
  name: 'search-role-user'
  params: {
    principalId: principalId
    roleDefinitionId: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
    principalType: 'User'
  }
}

module searchContribRoleUser 'core/security/role.bicep' = {
  name: 'search-contrib-role-user'
  params: {
    principalId: principalId
    roleDefinitionId: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
    principalType: 'User'
  }
}

module searchSvcContribRoleUser 'core/security/role.bicep' = {
  name: 'search-svccontrib-role-user'
  params: {
    principalId: principalId
    roleDefinitionId: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
    principalType: 'User'
  }
}

module searchRoleBackend 'core/security/role.bicep' = {
  name: 'search-role-backend'
  params: {
    principalId: backend.outputs.identityPrincipalId
    roleDefinitionId: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
    principalType: 'ServicePrincipal'
  }
}

output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId

output AZURE_OPENAI_SERVICE string = openAiServiceName
output AZURE_OPENAI_RESOURCE_GROUP string = openAiResourceGroupName
output AZURE_OPENAI_CHATGPT_DEPLOYMENT string = chatGptDeploymentName
output AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT string = embeddingsDeploymentName
output AZURE_OPENAI_API_KEY string = azureOpenaiApiKey
output AZURE_SEARCH_KEY string = azureSearchKey

output AZURE_SEARCH_INDEX string = searchIndexName

output BACKEND_URI string = backend.outputs.uri

output PROMPT_CONTENT_DB_NAME string = promptContentDbName
output PROMPT_CONTENT_DB string = promptContentDb
output LANGUAGE_MODEL string = languageModel
