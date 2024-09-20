import azure.functions as func
import logging
from openai import AzureOpenAI
import os
import requests
from PIL import Image
import json
import azure.cognitiveservices.speech as speechsdk
from azure.storage.blob import BlobServiceClient, BlobClient, ContentSettings
from io import BytesIO
from scipy.io import wavfile
import tempfile
import time



app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.route(route="edudalleapi")
def edudalleapi(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    try:
        req_body = req.get_json()
    except ValueError:
        pass
    else:
        dallePrompt = req_body.get('prompt')

    client = AzureOpenAI(
        api_version="2023-12-01-preview",  
        api_key="<your Dall-e subscription key here>",  
        azure_endpoint="<your Dall-e URL here>"
    )

    result = client.images.generate(
        model="Dalle3", # the name of your DALL-E 3 deployment
        prompt=dallePrompt,
        n=1
    )

    json_response = json.loads(result.model_dump_json())

   
    image_url = json_response["data"][0]["url"]  # extract image URL from response

    if image_url:
        return func.HttpResponse(f"{image_url}", status_code=200)
    else:
        return func.HttpResponse(
             "Error: Problem generating image",
             status_code=499
        )

@app.route(route="text_speech", auth_level=func.AuthLevel.FUNCTION)
def text_speech(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    name = req.params.get('name')
    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            name = req_body.get('name')
    
    
    """performs speech synthesis and gets the audio data from single request based stream."""
    # Creates an instance of a speech config with specified subscription key and service region.
    speech_config = speechsdk.SpeechConfig(subscription="<your speech to text subscription key here>", region="eastus")
    speech_config.speech_synthesis_voice_name = "en-US-AnaNeural"
    # Creates a speech synthesizer with a null output stream.
    # This means the audio output data will not be written to any output channel.
    # You can just get the audio from the result.
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)

    # Receives a text from console input and synthesizes it to result.
    text = name
    result = speech_synthesizer.speak_text_async(text).get()
    # Check result
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        print("Speech synthesized for text [{}]".format(text))
        audio_data_stream = speechsdk.AudioDataStream(result)
        
        dir_path = tempfile.gettempdir()
        timestr = time.strftime("%Y%m%d-%H%M%S")
        file = dir_path + "/"+ timestr+".mp3"
        audio_data_stream.save_to_wav_file(file)
        connection_string = "<your storage connection string>"
        output_container_name = "speech"
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container=output_container_name)
        with open(file=os.path.join(dir_path, timestr+'.mp3'), mode="rb") as data:
            blob_client = container_client.upload_blob(name=timestr+".mp3", data=data, overwrite=True)
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        print("Speech synthesis canceled: {}".format(cancellation_details.reason))
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            print("Error details: {}".format(cancellation_details.error_details))
    if name:
        return func.HttpResponse(f"{timestr}.mp3")
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )