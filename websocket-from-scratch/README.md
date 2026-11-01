# WebSocket From Scratch

An eight-stage course that builds the protocol a browser speaks after an HTTP
request turns into a long-lived connection. It starts with the Upgrade handshake
and ends with a session that can be fed any chunking of the same bytes: one byte
at a time, a frame at a time, or the handshake and the first message in one
packet.

The thesis is one sentence: **a WebSocket is what you read after the HTTP
request ends — every byte the server accepts is a frame the format allows, every
message is one the receiver can reconstruct, and every close is a code the peer
is allowed to send.**

There is no socket, no thread, no clock and no randomness in the course. A
WebSocket is a byte protocol, so the checker is the client and the world is the
bytes you hand it.

## Run it

```bash
python3 codecraft/cli.py run websocket-from-scratch
python3 codecraft/cli.py stage websocket-from-scratch 3
python3 codecraft/cli.py hint websocket-from-scratch
```

`cz run websocket-from-scratch` works too. Each stage has a template under
`stage_NN.py` and a finished version under `solutions/stage_NN.py`. The finished
versions are there to compare against *after* your own attempt; the checks never
import them.

## The stages

| # | File | What you build | The failure it prevents |
|---|---|---|---|
| 1 | `stage_01.py` | `parse_request`, `header_tokens`, `accept_key`, `accept` | Answering a request that never asked to upgrade, or computing an accept value the browser rejects |
| 2 | `stage_02.py` | `encode_header`, `decode_header` | Reading a length from the wrong width, or accepting a legal length written the long way |
| 3 | `stage_03.py` | `apply_mask`, `read_frame`, `write_frame` | Treating masking as encryption, or accepting an unmasked client frame |
| 4 | `stage_04.py` | control-frame rules, close codes, `ping`/`pong`/`close` | Sending 1005 on the wire, or fragmenting a ping |
| 5 | `stage_05.py` | `Assembler` | Starting a second message during a fragmented one, or losing the ping in the middle |
| 6 | `stage_06.py` | `validate_utf8`, `UTF8Stream` | Rejecting a character split across fragments, or accepting a surrogate |
| 7 | `stage_07.py` | `FrameStream` | A reader whose answer depends on where TCP happened to split the bytes |
| 8 | `stage_08.py` | `Session` | A handshake, an echo, a ping and a close that do not compose into a connection |

## The protocol in one screen

The client sends an HTTP/1.1 `GET` with `Upgrade: websocket`, a
`Sec-WebSocket-Key` (base64 of 16 random bytes), and version 13. The server
answers `101 Switching Protocols`, `Connection: Upgrade`, and
`Sec-WebSocket-Accept = base64(SHA-1(key + GUID))`. After the blank line, the
same connection carries frames.

A frame starts with a byte holding FIN and the opcode, then a byte holding MASK
and a seven-bit length. A length of 126 means two more length bytes; 127 means
eight more. A client masks every frame with a four-byte XOR key; a server never
masks. A message is one or more data frames: the first has opcode 1 (text) or 2
(binary), the rest have opcode 0 and continue until FIN. Control frames (8
close, 9 ping, 10 pong) may interrupt a fragmented message but cannot themselves
be fragmented or exceed 125 bytes. Text and close reasons must be valid UTF-8,
including when a character is split across fragments.

## What this course deliberately leaves out

TLS, `permessage-deflate`, HTTP/2's different framing, client-side handshake
generation, subprotocol semantics beyond selection, and the socket or asyncio
server around the session. Those are extensions or transport choices; the eight
stages are the part every implementation has to get right first.

## After the course

The natural next additions are a broadcast room (one session per connection, a
set of subscribers, and the same frame writer), a real `socket`/`asyncio` demo
that drops `Session` behind a TCP stream, and a browser page whose JavaScript
shows the same handshake and frames in the network panel. None of them change
the invariants the eight stages prove.
