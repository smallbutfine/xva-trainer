import os
import sys
import traceback
import multiprocessing



if __name__ == '__main__':
    multiprocessing.freeze_support()

    APP_VERSION = "1.0.0"

    PROD = False
    # PROD = True
    CPU_ONLY = False
    # CPU_ONLY = True



    # Imports and logger setup
    # ========================
    try:
        import asyncio
        import websockets
        import _thread
        import python.pyinstaller_imports
        import numpy

        import logging
        from logging.handlers import RotatingFileHandler
        import json
        from http.server import BaseHTTPRequestHandler, HTTPServer
        # from python.audio_post import run_audio_post, prepare_input_audio, mp_ffmpeg_output
        # import ffmpeg
    except:
        print(traceback.format_exc())
        with open("./DEBUG_err_imports.txt", "w+") as f:
            f.write(traceback.format_exc())

    # Pyinstaller hack
    # ================
    try:
        def script_method(fn, _rcb=None):
            return fn
        def script(obj, optimize=True, _frames_up=0, _rcb=None):
            return obj
        import torch.jit
        torch.jit.script_method = script_method
        torch.jit.script = script
        import torch
    except:
        with open("./DEBUG_err_import_torch.txt", "w+") as f:
            f.write(traceback.format_exc())
    # ================

    try:
        logger = logging.getLogger('serverLog')
        logger.setLevel(logging.DEBUG)
        # fh = RotatingFileHandler('{}/server.log'.format(os.path.dirname(os.path.realpath(__file__))), maxBytes=5*1024*1024, backupCount=2)
        fh = RotatingFileHandler('./server.log', maxBytes=5*1024*1024, backupCount=2)
        fh.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.ERROR)
        formatter = logging.Formatter('%(asctime)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        logger.addHandler(fh)
        logger.addHandler(ch)
        logger.info(f'New session. Version: {APP_VERSION}. Installation: {"CPU" if CPU_ONLY else "CPU+GPU"}')

        logger.orig_info = logger.info

        def prefixed_log (msg):
            logger.info(f'{logger.logging_prefix}{msg}')


        def set_logger_prefix (prefix=""):
            if len(prefix):
                logger.logging_prefix = f'[{prefix}]: '
                logger.log = prefixed_log
            else:
                logger.log = logger.orig_info

        logger.set_logger_prefix = set_logger_prefix
        logger.set_logger_prefix("")

    except:
        with open("./DEBUG_err_logger.txt", "w+") as f:
            f.write(traceback.format_exc())
        try:
            logger.info(traceback.format_exc())
        except:
            pass
    # ========================




    # ======================== Models manager
    try:
        from python.models_manager import ModelsManager
        models_manager = ModelsManager(logger, PROD, device="cpu")
    except:
        logger.info("Models manager failed to initialize")
        logger.info(traceback.format_exc())
    # ========================



    print("Models ready")
    logger.info("Models ready")

    async def websocket_handler(websocket, path):
        async for message in websocket:
            try:
                # logger.info(f'message: {message}')

                message = json.loads(message)
                model = message["model"]
                task = message["task"] if "task" in message else None
                data = message["data"] if "data" in message else None



                # DEBUG
                # ==================
                if model=="exit":
                    sys.exit()
                if model=="print":
                    logger.info(data)
                    await websocket.send("")
                if model=="print_and_return":
                    logger.info(data)
                    await websocket.send(data)
                if model=="getTimedData":
                    import time
                    await websocket.send("1")
                    time.sleep(1)
                    await websocket.send("2")
                    time.sleep(1)
                    await websocket.send("3")
                # ==================


                await models_manager.init_model(model, websocket)
                if task=="runTask":
                    await models_manager.models_bank[model].runTask(data, websocket=websocket)


            except KeyboardInterrupt:
                sys.exit()
            except:
                logger.info(traceback.format_exc())

    def get_or_create_eventloop ():
        try:
            return asyncio.get_event_loop()
        except RuntimeError as ex:
            if "There is no current event loop in thread" in str(ex):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return asyncio.get_event_loop()
    def startWebSocket ():
        try:
            logger.info("Starting websocket")
            get_or_create_eventloop()
            start_server = websockets.serve(websocket_handler, "localhost", 8000)
            asyncio.get_event_loop().run_until_complete(start_server)
            asyncio.get_event_loop().run_forever()
        except:
            import traceback
            with open("DEBUG_websocket.txt", "w+") as f:
                print(traceback.format_exc())







    # Server
    class Handler(BaseHTTPRequestHandler):
        def _set_response(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()

        def do_GET(self):
            returnString = "[DEBUG] Get request for {}".format(self.path).encode("utf-8")
            logger.info(returnString)
            self._set_response()
            self.wfile.write(returnString)

        def do_POST(self):
            post_data = ""
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = json.loads(self.rfile.read(content_length).decode('utf-8'))
                req_response = "POST request for {}".format(self.path)

                if self.path == "/stopServer":
                    logger.info("POST {}".format(self.path))
                    logger.info("STOPPING SERVER")
                    sys.exit()

                if self.path == "/setDevice":
                    logger.info("POST {}".format(self.path))
                    logger.info(post_data)

                    clearTheCache = False
                    if not CPU_ONLY and models_manager.device_label=="gpu" and post_data["device"]=="gpu":
                        clearTheCache = True
                        logger.info("CLEARING CACHE")
                        torch.cuda.empty_cache()

                    use_gpu = post_data["device"]=="gpu"
                    models_manager.set_device('cuda' if use_gpu else 'cpu')

                    if clearTheCache:
                        logger.info("CLEARING CACHE")
                        torch.cuda.empty_cache()


                if self.path == "/checkReady":
                    use_gpu = post_data["device"]=="gpu"
                    models_manager.set_device('cuda' if use_gpu else 'cpu')
                    req_response = "ready"


                self._set_response()
                self.wfile.write(req_response.encode("utf-8"))
            except Exception as e:
                with open("./DEBUG_request.txt", "w+") as f:
                    f.write(traceback.format_exc())
                    f.write(str(post_data))
                logger.info("Post Error:\n {}".format(repr(e)))
                print(traceback.format_exc())
                logger.info(traceback.format_exc())

    try:
        server = HTTPServer(("",8001), Handler)
    except:
        with open("./DEBUG_server_error.txt", "w+") as f:
            f.write(traceback.format_exc())
        logger.info(traceback.format_exc())
    try:
        logger.info("About to start websocket")
        _thread.start_new_thread(startWebSocket, ())
        logger.info("Started websocket")

        # plugin_manager.run_plugins(plist=plugin_manager.plugins["start"]["post"], event="post start", data=None)
        print("Server ready")
        logger.info("Server ready")
        server.serve_forever()


    except KeyboardInterrupt:
        pass
    server.server_close()