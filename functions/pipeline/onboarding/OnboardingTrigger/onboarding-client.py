import requests
import json

# The following mock client imitates the CLI during the onboarding scenario for new images.
# The CLI uploads images to a temporary blob store, then gets a list of URLs to those images and
# passes it to an HTTP trigger function, which calls the DAL to create rows in the database.

print("\nTest client for CLI Onboarding scenario")
print('-' * 40)

print("Now executing POST request to onboard images...")

#functionURL = "https://onboardinghttptrigger.azurewebsites.net/api/onboardingtrigger?code=mYOL/zprAqL5TlU21WJA4VWFJdf0oqOnf0fhMtveJsVEampMqrLhGw=="
#functionURL = "https://onboardinghttptrigger.azurewebsites.net/api/OnboardingHttpTrigger"
functionURL = "https://mtarngfunc-test.azurewebsites.net/api/onboarding?code=ezQ4rW/DvaNtm6DlHZ7XQp1Enrtao3WpsW4FFR5V/nFLVb9vq4P7PQ=="
#functionURL = "http://localhost:7071/api/OnboardingTrigger"
headers = {"Content-Type": "application/json"}
# urlList = { "imageUrls": ["http://www.whitneyway.com/Images/15/2017%20Puppies%20in%20Easter%20basket%204-16-17_800.JPG",
#                          "http://allpetcages.com/wp-content/uploads/2017/06/puppy-whelping-box.jpg",
#                          "http://78.media.tumblr.com/eea2f882ec08255e40cecaf8ca1d4543/tumblr_nmxjbjIK141qi4ucgo1_500.jpg"] }
with open('urlList.json', 'r') as urls:
    urlList=json.loads(urls.read())

response = requests.post(url = functionURL, headers=headers, json = urlList)

print("Completed POST request.")

raw_response = response.text
response_array = raw_response.split(", ")
response_output = "\n".join(response_array)

print(f"Response status code: {response.status_code}")
print(f"Response: {response_output}")