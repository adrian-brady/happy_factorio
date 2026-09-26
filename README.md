# happy_factorio
Edits factorio graphics to be happier and more pastel colored


# Instructions
There are 2 files to download: pastel-factorio.zip and pastel-water_0.1.0.zip

1) put pastel-water_0.1.0.zip in your factorio mod folder. Don't unzip it, just place it there. This will make the water a lighter cyan color. You can adjust it's strength in the mod settings in game.

2) unzip pastel-factorio.zip and inside the pastel-factorio directory create a new folder called "data". Then within "data" create two new folders "base" and "core". This is where you will paste the "graphics" folders from the factorio game installation. Inside the factorio installation you will see data/base/graphics and data/core/graphics. You should paste the "graphics" folders from each of those places into your new folders you made, so that you have data/base/graphics and data/core/graphics within your pastel-factorio project that match the ones in your installation.

   Your pastel-factorio directory should now look like:
```text
pastel-factorio/
├── config/
├── data/
│   └── base/
│       └── graphics/
│   └── core/
│       └── graphics/
├── pastel/
├── plan.md
├── README.md
└── requirements.txt
```
  
3) To run the code, you need python installed (you can check if you have it installed by typing python or python3. Depending on which command works, replace future "python" commands with "python3")

  [OPTIONAL]: there are only a few python libraries in requirements.txt and they are commonly used, but if you have a specific python installation that you don't want modified, feel free to set up a venv before running the following commands.
  
  open your terminal (or command prompt) and navigate to your pastel-factorio directory and run the command
```
pip install -r requirements.txt
```

4) run command
```
python -m pastel build
```
This command can take up to 10 minutes to run. It is going over all the graphics files in data/base/graphics and data/core/graphics and creating modified verisons.
When the command completes, you should have 2 new directories: data/base/updated_graphics & data/core/updated_graphics

5) go to your factorio installation and (Optional: rename your graphics folders in the original installation to ORIGINAL_graphics so you have a backup of the originals. Worst case if you just delete them and want to return to the original grahpics you can reinstall factorio) paste in the updated_graphics folders into their respective locations and rename them to just be "graphics". The game should not be aware you've changed anything as you've just replaced the original graphics folders and it has all the same files (with just different colors in the .pngs).

6) launch factorio and enjoy!


# NOTE: I do not plan to expand or maintain this, so will likely not regularly check in on this github repo. This is a one-time sharing as is :) Feel free to fork it or expand on it or do whatever you want!
