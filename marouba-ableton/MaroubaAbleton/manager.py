from __future__ import absolute_import, print_function

import logging
import os

from ableton.v2.control_surface import ControlSurface

from .maroubaosc import OSC_LISTEN_PORT, OSC_RESPONSE_PORT, MaroubaOscServer


logger = logging.getLogger("marouba-ableton")


class Manager(ControlSurface):
    """Marouba's Ableton Remote Script bootstrap.

    This intentionally mirrors AbletonOSC's no-thread tick loop. Ableton's
    embedded Python environment can be unhappy with background threads, so the
    OSC server is drained from Live's scheduled control-surface callback.
    """

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._log_handler = None
        self._osc_server = None
        self._start_logging()
        try:
            self._osc_server = MaroubaOscServer()
            self._install_handlers()
            self.schedule_message(1, self._tick)
            self.show_message(
                "MaroubaAbleton: Listening for OSC on port %d" % OSC_LISTEN_PORT
            )
            logger.info("MaroubaAbleton loaded cleanly")
        except Exception as error:
            logger.exception("MaroubaAbleton failed to start")
            self.show_message("MaroubaAbleton failed to start: %s" % error)

    def _start_logging(self):
        module_path = os.path.dirname(os.path.realpath(__file__))
        log_dir = os.path.join(module_path, "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        log_path = os.path.join(log_dir, "marouba-ableton.log")
        self._log_handler = logging.FileHandler(log_path)
        self._log_handler.setLevel(logging.INFO)
        self._log_handler.setFormatter(
            logging.Formatter("(%(asctime)s) [%(levelname)s] %(message)s")
        )
        logger.setLevel(logging.INFO)
        logger.addHandler(self._log_handler)

    def _install_handlers(self):
        self._osc_server.add_handler("/marouba/health", self._health)
        self._osc_server.add_handler("/live/test", self._test)
        self._osc_server.add_handler("/live/application/get/version", self._version)

    def _health(self, _params):
        return ("ok", "marouba-ableton")

    def _test(self, _params):
        self.show_message("MaroubaAbleton: OSC OK")
        return ("ok",)

    def _version(self, _params):
        app = self.application()
        return (
            app.get_major_version(),
            app.get_minor_version(),
            app.get_bugfix_version(),
        )

    def _tick(self):
        if self._osc_server is not None:
            self._osc_server.process()
        self.schedule_message(1, self._tick)

    def disconnect(self):
        logger.info("MaroubaAbleton disconnecting")
        if self._osc_server is not None:
            self._osc_server.shutdown()
        if self._log_handler is not None:
            logger.removeHandler(self._log_handler)
            self._log_handler.close()
        super(Manager, self).disconnect()
