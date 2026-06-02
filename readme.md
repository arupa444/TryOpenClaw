# TryOpenClaw

This repository is all about openclaw.

It currently contains the 'myApp' directory, which was added from the user's desktop.


..\.venv\Scripts\python.exe -c "import duckdb; c=duckdb.connect('dronisight.duckdb'); c.execute(\"UPDATE pole_images SET abs_path = 'E:/hydPoleDetection' || substr(abs_path, length('/Volumes/Atrisol_D2/hydPoleDetection')+1) WHERE abs_path LIKE '/Volumes/Atrisol_D2/hydPoleDetection/%'\"); c.execute(\"UPDATE pole_images SET abs_path = 'E:/phase1' || substr(abs_path, length('/Volumes/Atrisol_D2/phase1')+1) WHERE abs_path LIKE '/Volumes/Atrisol_D2/phase1/%'\"); print('rows now:', c.execute('SELECT count(*) FROM pole_images WHERE abs_path LIKE \'E:/%\'').fetchone()[0])"
