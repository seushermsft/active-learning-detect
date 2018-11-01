import requests
import json

print("\nTest client for CLI Onboarding scenario\n-------------------------------------\n")

print("Now executing cURL POST request to onboard images...")

functionURL = "http://localhost:7071/api/TestHTTPTrigger"
urlList = { "imageUrls": ["url1", "url2", "url3"] }

response = requests.post(url = functionURL, data = json.dumps(urlList))

print("Completed cURL POST request.")

postresponse = response.text

print("Response: " + response.text)
