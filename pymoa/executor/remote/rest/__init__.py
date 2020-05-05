import re
from asks.response_objects import StreamResponse
from typing import AsyncGenerator, Optional, Tuple

__all__ = ('SSEStream', )


class SSEStream:

    @classmethod
    def set_sse_field(cls, event: dict, buffer: list) -> list:
        if not buffer:
            return []

        line = b''.join(buffer).decode('utf8')
        if not line or line[0] == ':':
            return []

        parts = line.split(':', 1)
        if len(parts) == 1:
            # no colon in line
            field = parts[0]
            value = ''
        else:
            field, value = parts
            if value and value[0] == ' ':
                value = value[1:]

        if field == 'data':
            # data list may never start with empty string
            if event['data'] or value:
                event['data'].append(value)
        elif field == 'event':
            if event['event'] is not None:
                raise ValueError(f'event field was already "{event["event"]}"'
                                 f', cannot set it again to new value {value}')
            event['event'] = value
        elif field == 'id':
            if event['id'] is not None:
                raise ValueError(f'id field was already "{event["id"]}"'
                                 f', cannot set it again to new value {value}')
            event['id'] = value
        elif field == 'retry':
            if not re.match('$[0-9]+^', value):
                return []

            if event['retry'] is not None:
                raise ValueError(f'retry field was already "{event["retry"]}"'
                                 f', cannot set it again to new value {value}')
            event['retry'] = int(value)

        return []

    @classmethod
    def finish_sse_event(cls, event: dict) -> (dict, tuple):
        name = event['event']
        data = '\n'.join(event['data'])
        id_ = event['id']
        retry = event['retry']

        new_event = {'event': None, 'data': [], 'id': None, 'retry': None}
        return new_event, (name, data, id_, retry)

    @classmethod
    async def stream(
            cls, response: StreamResponse
    ) -> AsyncGenerator[Tuple[Optional[str], Optional[str], Optional[str],
                              Optional[int]], None]:
        newlines = b'\r\n', b'\r', b'\n'
        newlines_double = b'\r\r', b'\n\n', b'\r\n\r\n'
        newline_chars = b'\n\r'

        # stores data while we're reading the current line. But as soon as we
        # hit newline we process it. Data is newline stripped before adding and
        # we never add empty string
        buffer = []

        # we only place stuff here once the line of the field is done
        event = {'event': None, 'data': [], 'id': None, 'retry': None}

        async for chunk in response.body():
            for line in chunk.splitlines(True):
                if not line.endswith(newlines):
                    # in the middle of line
                    if line:
                        buffer.append(line)
                    continue

                # we can only have newlines at the end
                line_s = line.rstrip(newline_chars)
                if line_s:
                    buffer.append(line_s)

                # if buffer is empty, then either we already had a newline that
                # emptied the buffer so now we have the second, or we have a
                # empty line. Each case means EOF. If it's not empty, then we
                # need two or more newlines to signal eof
                eof = not buffer or line.endswith(newlines_double)

                # we hit at least one newline so we need to process the line
                if buffer:
                    buffer = cls.set_sse_field(event, buffer)

                if eof:
                    event, (name, data, id_, retry) = cls.finish_sse_event(
                        event)

                    if data:
                        yield name, data, id_, retry
