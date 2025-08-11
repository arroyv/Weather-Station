@reboot cd $HOME/Weather-Station && $HOME/Weather-Station/venv/bin/python $HOME/Weather-Station/run_weather_station.py >> $HOME/Weather-Station/run_weather_station.log 2>&1
@reboot cd $HOME/Weather-Station && $HOME/Weather-Station/venv/bin/python $HOME/Weather-Station/app.py >> $HOME/Weather-Station/app.log 2>&1

