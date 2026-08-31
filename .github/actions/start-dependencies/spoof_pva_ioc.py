#!/usr/bin/env python3
from p4p.nt import NTScalar
from p4p.server import Server
from p4p.server.thread import SharedPV


def main():
    pv = SharedPV(
        nt=NTScalar("d"),
        initial=0.0,
    )

    @pv.put
    def handle_put(pv, op):
        pv.post(op.value())
        op.done()

    Server.forever(
        providers=[
            {
                "XF:27ID1-ES{PANDA:1}:PVI": pv,
            }
        ]
    )


if __name__ == "__main__":
    main()