from flask import Flask, render_template
from dash import dcc, html, Dash, no_update, callback_context
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go
import numpy as np
import librosa
import base64
import io

# Initialize the Flask app
server = Flask(__name__)

# Initialize the Dash app
app = Dash(__name__, server=server, url_base_pathname='/analyse/')

# Declare server for Heroku deployment. Needed for Procfile.
server = app.server

app.layout = html.Div([
    html.H1('Amplitude Analysis', style={'textAlign': 'center'}),
    html.Div(
        dcc.Upload(
            id='upload-audio',
            children=html.Button('Upload Audio File', style={'fontSize': 20}),
            multiple=False
        ),
        style={'textAlign': 'center', 'marginBottom': '20px'}
    ),
    html.Div(id='audio-player', style={'textAlign': 'center'}),  # Placeholder for audio player
    dcc.Loading(
        id='loading',
        type='default',
        children=dcc.Graph(id='amplitude-plot', config={
            'modeBarButtonsToAdd': ['drawrect', 'eraseshape', 'zoom', 'zoomIn', 'zoomOut', 'resetScale2d'],
            'displaylogo': False
        })
    ),
    html.Div([
        'Start Time (s): ',
        dcc.Input(id='start-time', type='number', value=0, step=0.0001, style={'fontSize': 20, 'height': '25px', 'width': '100px'}),
        html.Span(' ', style={'margin': '0 10px'}),
        ' End Time (s): ',
        dcc.Input(id='end-time', type='number', value=0, step=0.0001, style={'fontSize': 20, 'height': '25px', 'width': '100px'}),
        html.Span(' ', style={'margin': '0 10px'}),
        html.Button('Confirm', id='confirm-button', n_clicks=0, style={'fontSize': 20, 'height': '30px'})
    ], style={'textAlign': 'center', 'fontSize': 20, 'marginBottom': 10}),
    html.Div(id='output-container', style={'textAlign': 'center', 'fontSize': 20}),
    
    dcc.Loading(
        id='loading-magnitude',
        type='default',
        children=dcc.Graph(id='fft-magnitude-plot', config={
            'modeBarButtonsToAdd': ['eraseshape', 'zoom', 'zoomIn', 'zoomOut', 'resetScale2d'],
            'displaylogo': False
        })
    ),
    dcc.Loading(
        id='loading-phase',
        type='default',
        children=dcc.Graph(id='fft-phase-plot')
    ),
    dcc.Loading(
        id='loading-inverse',
        type='default',
        children=dcc.Graph(id='inverse-amplitude-plot')
    ),
    dcc.Store(id='line-color-update', data=False)
])

def parse_contents(contents):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    audio_data, sr = librosa.load(io.BytesIO(decoded), sr=None)
    
    # Calculate the amplitude
    amplitude = audio_data
    time = np.linspace(0, len(audio_data) / sr, num=len(audio_data))

    # Convert amplitude and time to standard Python float
    amplitude = amplitude.astype(float)
    time = time.astype(float)

    # Create the initial amplitude plot
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=time, y=amplitude, mode='lines', name='Amplitude'))
    fig.update_layout(
        title=dict(text='Audio Waveform', font=dict(weight='bold')),
        xaxis_title='Time (s)',
        yaxis_title='Amplitude',
        dragmode='drawrect',
        newshape=dict(
            line=dict(color='red')
        )
    )
    
    return fig, time, amplitude, sr, content_string

@app.callback(
    Output('line-color-update', 'data'),
    [Input('confirm-button', 'n_clicks')],
    [State('line-color-update', 'data')]
)
def set_line_color_update(n_clicks, current_status):
    if n_clicks > 0:
        return not current_status
    return current_status

@app.callback(
    [Output('amplitude-plot', 'figure'),
     Output('audio-player', 'children'),
     Output('start-time', 'value'),
     Output('end-time', 'value')],
    [Input('upload-audio', 'contents'),
     Input('confirm-button', 'n_clicks'),
     Input('amplitude-plot', 'relayoutData')],
    [State('amplitude-plot', 'figure')]
)
def update_amplitude_plot(contents, n_clicks, relayoutData, figure):
    ctx = callback_context

    # Check if the trigger was the upload button
    if ctx.triggered and ctx.triggered[0]['prop_id'].split('.')[0] == 'upload-audio':
        if contents is not None:
            amplitude_fig, time, amplitude, sr, content_string = parse_contents(contents)
            amplitude_fig.update_layout(
                shapes=[]
            )
            audio_player = html.Audio(
                src=f'data:audio/wav;base64,{content_string}',
                controls=True,
                style={'width': '25%'}
            )
            return amplitude_fig, audio_player, no_update, no_update

    # Check if the trigger was the confirm button
    if ctx.triggered and ctx.triggered[0]['prop_id'].split('.')[0] == 'confirm-button':
        if n_clicks > 0 and figure and 'layout' in figure and 'shapes' in figure['layout']:
            for shape in figure['layout']['shapes']:
                shape['line']['color'] = 'rgba(255, 0, 0, 0)'
                shape['line']['width'] = 1
            return figure, no_update, no_update, no_update

    # Check if the trigger was the rectangle drawing
    if ctx.triggered and ctx.triggered[0]['prop_id'].split('.')[0] == 'amplitude-plot':
        if 'shapes' in relayoutData:
            shape = relayoutData['shapes'][-1]  # Get the last drawn shape
            x0, x1 = shape['x0'], shape['x1']

            # Get the y-axis range
            if figure and 'layout' in figure and 'yaxis' in figure['layout']:
                yaxis_range = figure['layout']['yaxis']['range']
                y0 = yaxis_range[0]
                y1 = yaxis_range[1]
                
                # Update the shape's y0 and y1 to fit the y-axis range
                shape['y0'] = y0
                shape['y1'] = y1

                # Update figure with new shape boundaries
                figure['layout']['shapes'][-1]['y0'] = y0
                figure['layout']['shapes'][-1]['y1'] = y1

                start_time = float(format(min(x0, x1), '.5f'))
                end_time = float(format(max(x0, x1), '.5f'))
                return figure, no_update, start_time, end_time

    # Preserve the existing figure if no update
    if figure is not None:
        return figure, no_update, no_update, no_update

    return go.Figure(), '', no_update, no_update

@app.callback(
    [Output('output-container', 'children'),
     Output('fft-magnitude-plot', 'figure'),
     Output('fft-phase-plot', 'figure'),
     Output('inverse-amplitude-plot', 'figure')],
    [Input('confirm-button', 'n_clicks')],
    [State('amplitude-plot', 'figure'),
     State('start-time', 'value'),
     State('end-time', 'value')]
)
def update_fft_and_inverse_plots(n_clicks, figure, start_time, end_time):
    if figure is None or 'data' not in figure or len(figure['data']) == 0:
        return 'Upload an audio file to analyze.', go.Figure(), go.Figure(), go.Figure()

    time = np.array(figure['data'][0]['x'])
    amplitude = np.array(figure['data'][0]['y'])
    sr = 1 / (time[1] - time[0])
    
    x0, x1 = None, None

    if n_clicks > 0 and start_time is not None and end_time is not None:
        x0 = start_time
        x1 = end_time

    if x0 is not None and x1 is not None:
        if x0 > x1:
            x0, x1 = x1, x0

        selected_points = [{'time': time[i], 'amplitude': amplitude[i]} for i in range(len(time)) if x0 <= time[i] <= x1]

        amplitudes = np.array([point['amplitude'] for point in selected_points])
        
        # Ensure the length of the signal is even
        if len(amplitudes) % 2 != 0:
            amplitudes = np.append(amplitudes, 0)

        N = len(amplitudes)
        yf_segment = np.fft.fft(amplitudes)
        xf_segment = np.fft.fftfreq(N, 1 / sr)

        idx = np.arange(0, N // 2)
        xf_segment = xf_segment[idx]
        yf_segment_magnitude = np.abs(yf_segment)
        yf_segment_phase = np.angle(yf_segment)

        # Create magnitude spectrum plot
        fft_magnitude_fig = go.Figure()
        fft_magnitude_fig.add_trace(go.Scatter(x=xf_segment, y=yf_segment_magnitude[idx], mode='lines', name='Magnitude'))
        fft_magnitude_fig.update_layout(
            title=dict(text='<span style="color:red"> DFT: </span> Frequency-Domain Signal (Magnitude Spectrum)', font=dict(weight='bold')),
            xaxis_title='Frequency (Hz)',
            yaxis_title='Magnitude',
            paper_bgcolor='rgb(249,249,249)'
        )

        # Create phase spectrum plot
        fft_phase_fig = go.Figure()
        fft_phase_fig.add_trace(go.Scatter(x=xf_segment, y=yf_segment_phase[idx], mode='lines', name='Phase'))
        fft_phase_fig.update_layout(
            title=dict(text='<span style="color:red"> DFT: </span> Frequency-Domain Signal (Phase Spectrum)', font=dict(weight='bold')),
            xaxis_title='Frequency (Hz)',
            yaxis_title='Phase (radians)',
            paper_bgcolor='rgb(249,249,249)'
        )

        # Combine magnitude and phase to reconstruct the complex spectrum
        X_reconstructed = yf_segment_magnitude * np.exp(1j * yf_segment_phase)

        # Compute inverse FFT
        x_reconstructed = np.fft.ifft(X_reconstructed).real

        # Create time domain
        time_inverse = np.linspace(0, len(x_reconstructed) / sr, num=len(x_reconstructed))

        # Create inverse amplitude plot
        inverse_amplitude_fig = go.Figure()
        inverse_amplitude_fig.add_trace(go.Scatter(x=time_inverse, y=x_reconstructed, mode='lines', name='Inverse Amplitude'))
        inverse_amplitude_fig.update_layout(
            title=dict(text='Reconstructed Time-Domain Signal from <span style="color:red"> IDFT: </span> ', font=dict(weight='bold')),
            xaxis_title='Time (s)',
            yaxis_title='Amplitude'
        )

        return f'Selected Region: Start = {x0:.5f}, End = {x1:.5f}. Number of points selected: {len(selected_points)}.', fft_magnitude_fig, fft_phase_fig, inverse_amplitude_fig

    return 'Select a region to see the coordinates.', go.Figure(), go.Figure(), go.Figure()

# Define Flask route
@server.route('/')
def index():
    return render_template('index.html')

@server.route('/analyse.html')
def render_analysis():
    return app.index()

# Run the server
if __name__ == '__main__':
    server.run(debug=True)