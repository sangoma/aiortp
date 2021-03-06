import argparse
import asyncio
import logging

import aiortp
import aiosip

sip_config = {
    'srv_host': 'xxxxxx',
    'srv_port': '7000',
    'realm': 'XXXXXX',
    'user': 'YYYYYY',
    'pwd': 'ZZZZZZ',
    'local_ip': '127.0.0.1',
    'local_port': 6000
}


async def on_invite(request, message):
    scheduler = aiortp.RTPScheduler()
    stream = scheduler.create_new_stream((sip_config['local_ip'], 49711))
    await stream.negotiate(message.payload)

    print('Call ringing!')
    dialog = await request.prepare(status_code=100)
    await dialog.reply(message, status_code=180)

    await asyncio.sleep(1)
    await dialog.reply(message,
                       status_code=200,
                       headers={'Content-Type': 'application/sdp'},
                       payload=str(stream.describe()))
    print('Call started!')

    async for message in dialog:
        await dialog.reply(message, 200)
        if message.method == 'BYE':
            break

    # print(stream.protocol.packets)
    from aiortp.stats import StreamStats
    stats = StreamStats(stream.protocol.packets)

    import numpy as np
    print("codecs:", stats.codecs)
    print("duplicates:", stats.duplicates)
    print("loss:", stats.loss)
    print("length:", stats.duration.total_seconds())
    print("max delta:", np.max(stats.deltas))
    print("mean delta:", np.mean(stats.deltas))
    print("max jitter:", np.max(stats.jitter))
    print("mean jitter:", np.mean(stats.jitter))
    print("rms:", stats.rms)


def start(app, protocol):
    app.loop.run_until_complete(
        app.run(
            protocol=protocol,
            local_addr=(sip_config['local_ip'], sip_config['local_port'])))

    print('Serving on {} {}'.format(
        (sip_config['local_ip'], sip_config['local_port']), protocol))

    try:
        app.loop.run_forever()
    except KeyboardInterrupt:
        pass

    print('Closing')
    app.loop.run_until_complete(app.close())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--protocol', default='udp')
    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    app = aiosip.Application(loop=loop)
    app.dialplan.add_user('aiosip', {
        'INVITE': on_invite
    })

    if args.protocol == 'udp':
        start(app, aiosip.UDP)
    elif args.protocol == 'tcp':
        start(app, aiosip.TCP)
    elif args.protocol == 'ws':
        start(app, aiosip.WS)
    else:
        raise RuntimeError("Unsupported protocol: {}".format(args.protocol))

    loop.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
