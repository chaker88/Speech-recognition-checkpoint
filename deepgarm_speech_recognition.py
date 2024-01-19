import json
import queue
import pydub
import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode
import io

from deepgram import DeepgramClient,PrerecordedOptions,FileSource

DEEPGRAM_API_KEY ='592375b5d564169a2040dbdf4a064ae9d18fbf05'    

def transcribe_audio_chunks(audio_chunks, language):
    try:
        #initialisation deepgram
        deepgram = DeepgramClient(DEEPGRAM_API_KEY)
        model=""
        if language=='it':
            model="enhanced"
        else:
            model="nova-2"
        
        options = PrerecordedOptions(
            model=model,
            language=language,
            smart_format=True,
        )
        #initialisation empty wave object file
        wav_file_object = io.BytesIO()
        #save the wave file object in mermory
        audio_chunks.export(wav_file_object, format="wav")
       
        #converting to deepgram source
        payload: FileSource = {
            "buffer": wav_file_object,
        }  # type: ignore

        response = deepgram.listen.prerecorded.v("1").transcribe_file(payload, options)
        
        return response

    except Exception as e:
        print(f'Exception: {e}')
        return None
def save_transcript_to_file(transcript_text, file_name="speech_recognition/transcript.txt"):
    try:
        with open(file_name, 'w') as file:
            file.write(transcript_text)
        return True
    except Exception as e:
        print(f"Error saving transcript: {e}")
        return False

def extract_transcript_confidence(json_data):
    data = json.loads(json_data)  # Parse JSON string

    results = data.get('results')
    if results:
        channels = results.get('channels')
        if channels and len(channels) > 0:
            channel = channels[0]
            alternatives = channel.get('alternatives')
            if alternatives and len(alternatives) > 0:
                first_alternative = alternatives[0]
                transcript = first_alternative.get('transcript')
                confidence = first_alternative.get('confidence')
                return transcript, confidence
    return None, None

def main():
     # Sidebar for language selection
    selected_language = st.sidebar.selectbox(
        "Select Language for Transcription",
        ["en", "it", "fr"]  
    )
    
    st.session_state['language_to_transcript']=selected_language
    
    #Using webrtc for listen to microphone audio
    webrtc_ctx = webrtc_streamer(
        key="sendonly-audio",
        mode=WebRtcMode.SENDONLY,
        audio_receiver_size=256,
        rtc_configuration={
            "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
        },
        media_stream_constraints={
            "audio": True,
        },
    )

    if "audio_buffer" not in st.session_state:
        st.session_state["audio_buffer"] = pydub.AudioSegment.empty()

    status_indicator = st.empty()

    while True:
        if webrtc_ctx.audio_receiver:
            try:
                audio_frames = webrtc_ctx.audio_receiver.get_frames(timeout=1)
            except queue.Empty:
                status_indicator.write("No frame arrived.")
                continue

            status_indicator.write("Running. Say something!")

            sound_chunk = pydub.AudioSegment.empty()
            for audio_frame in audio_frames:
                sound = pydub.AudioSegment(
                    data=audio_frame.to_ndarray().tobytes(),
                    sample_width=audio_frame.format.bytes,
                    frame_rate=audio_frame.sample_rate,
                    channels=1 if audio_frame.layout.name == 'mono' else 2,
                )
                sound_chunk += sound
            if len(sound_chunk) > 0:
                st.session_state["audio_buffer"] += sound_chunk
        else:
            status_indicator.write("AudioReceiver stop.")
            break
        
    audio_buffer = st.session_state["audio_buffer"]

    if not webrtc_ctx.state.playing and len(audio_buffer) > 0:
        st.info("Performing speech recognition with Deepgram...")

        # Send audio data to Deepgram for transcription
        transcription = transcribe_audio_chunks(audio_buffer,st.session_state["language_to_transcript"])
        if transcription:
            formatted_json = json.dumps(transcription.to_dict(), indent=4)
            
            #extract transcription and confidance
            transc,confi=extract_transcript_confidence(formatted_json)
            print(formatted_json)
            st.success("transcription success")
            st.write('transcription:',transc)
            st.write('confidance:',confi)
            #save the transcription text to file 
            save_transcript_to_file(transc)
        else:
            st.info("Writing WAV to disk")
        
        
        audio_buffer.export("speech_recognition/temp.wav", format="wav")

        # Reset session states
        st.session_state["audio_buffer"] = pydub.AudioSegment.empty()
        st.session_state['language_to_transcript']=""


if __name__ == "__main__":
    
    main()
