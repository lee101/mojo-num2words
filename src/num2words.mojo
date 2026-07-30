"""English number-to-words kernels over caller-owned packed buffers."""

comptime BPtr = UnsafePointer[UInt8, AnyOrigin[mut=True]]
comptime IPtr = UnsafePointer[Int64, AnyOrigin[mut=True]]


struct Writer:
    var dst_addr: Int
    var capacity: Int
    var position: Int

    def __init__(out self, dst_addr: Int, capacity: Int):
        self.dst_addr = dst_addr
        self.capacity = capacity
        self.position = 0

    def byte(mut self, value: UInt8):
        if self.position < self.capacity:
            var dst = BPtr(unsafe_from_address=self.dst_addr)
            dst[self.position] = value
        self.position += 1

    def literal(mut self, value: StringSlice):
        var data = value.as_bytes()
        for i in range(len(data)):
            self.byte(data[i])


def write_small_word(mut writer: Writer, value: Int):
    if value == 0:
        writer.literal("zero")
    elif value == 1:
        writer.literal("one")
    elif value == 2:
        writer.literal("two")
    elif value == 3:
        writer.literal("three")
    elif value == 4:
        writer.literal("four")
    elif value == 5:
        writer.literal("five")
    elif value == 6:
        writer.literal("six")
    elif value == 7:
        writer.literal("seven")
    elif value == 8:
        writer.literal("eight")
    elif value == 9:
        writer.literal("nine")
    elif value == 10:
        writer.literal("ten")
    elif value == 11:
        writer.literal("eleven")
    elif value == 12:
        writer.literal("twelve")
    elif value == 13:
        writer.literal("thirteen")
    elif value == 14:
        writer.literal("fourteen")
    elif value == 15:
        writer.literal("fifteen")
    elif value == 16:
        writer.literal("sixteen")
    elif value == 17:
        writer.literal("seventeen")
    elif value == 18:
        writer.literal("eighteen")
    else:
        writer.literal("nineteen")


def write_tens_word(mut writer: Writer, value: Int):
    if value == 2:
        writer.literal("twenty")
    elif value == 3:
        writer.literal("thirty")
    elif value == 4:
        writer.literal("forty")
    elif value == 5:
        writer.literal("fifty")
    elif value == 6:
        writer.literal("sixty")
    elif value == 7:
        writer.literal("seventy")
    elif value == 8:
        writer.literal("eighty")
    else:
        writer.literal("ninety")


def write_scale(mut writer: Writer, scale: Int):
    if scale == 1:
        writer.literal("thousand")
    elif scale == 2:
        writer.literal("million")
    elif scale == 3:
        writer.literal("billion")
    elif scale == 4:
        writer.literal("trillion")
    elif scale == 5:
        writer.literal("quadrillion")
    elif scale == 6:
        writer.literal("quintillion")


def write_under_hundred(mut writer: Writer, value: Int):
    if value < 20:
        write_small_word(writer, value)
        return
    write_tens_word(writer, value // 10)
    if value % 10 != 0:
        writer.byte(UInt8(45))
        write_small_word(writer, value % 10)


def write_group(mut writer: Writer, value: Int):
    if value >= 100:
        write_small_word(writer, value // 100)
        writer.literal(" hundred")
        if value % 100 != 0:
            writer.literal(" and ")
            write_under_hundred(writer, value % 100)
    else:
        write_under_hundred(writer, value)


def write_cardinal_positive(mut writer: Writer, value: Int):
    if value == 0:
        writer.literal("zero")
        return
    var divisor = 1000000000000000000
    var scale = 6
    var wrote_group = False
    while divisor > 0:
        var group = (value // divisor) % 1000
        if group != 0:
            if wrote_group:
                if scale == 0 and group < 100:
                    writer.literal(" and ")
                else:
                    writer.literal(", ")
            write_group(writer, group)
            if scale != 0:
                writer.byte(UInt8(32))
                write_scale(writer, scale)
            wrote_group = True
        divisor //= 1000
        scale -= 1


def write_cardinal(mut writer: Writer, value: Int):
    var magnitude = value
    if value < 0:
        writer.literal("minus ")
        magnitude = -value
    write_cardinal_positive(writer, magnitude)


def write_ordinal_word(mut writer: Writer, value: Int):
    if value == 0:
        writer.literal("zeroth")
    elif value == 1:
        writer.literal("first")
    elif value == 2:
        writer.literal("second")
    elif value == 3:
        writer.literal("third")
    elif value == 4:
        writer.literal("fourth")
    elif value == 5:
        writer.literal("fifth")
    elif value == 6:
        writer.literal("sixth")
    elif value == 7:
        writer.literal("seventh")
    elif value == 8:
        writer.literal("eighth")
    elif value == 9:
        writer.literal("ninth")
    elif value == 10:
        writer.literal("tenth")
    elif value == 11:
        writer.literal("eleventh")
    else:
        writer.literal("twelfth")


def last_word_start(writer: Writer) -> Int:
    var dst = BPtr(unsafe_from_address=writer.dst_addr)
    # A truncated cardinal can have a logical position beyond the caller's row.
    # Scan only bytes that Writer actually stored; the exported function will
    # subsequently report the undersized stride.
    var position = min(writer.position, writer.capacity)
    while position > 0:
        var value = dst[position - 1]
        if value == UInt8(32) or value == UInt8(45):
            break
        position -= 1
    return position


def write_ordinal(mut writer: Writer, value: Int):
    write_cardinal_positive(writer, value)
    var last_two = value % 100
    if value == 0:
        writer.position = 0
        write_ordinal_word(writer, 0)
    elif last_two >= 1 and last_two <= 12:
        writer.position = last_word_start(writer)
        write_ordinal_word(writer, last_two)
    elif last_two > 20 and last_two % 10 >= 1:
        writer.position = last_word_start(writer)
        write_ordinal_word(writer, last_two % 10)
    elif last_two >= 20 and last_two % 10 == 0:
        writer.position -= 1
        writer.literal("ieth")
    else:
        writer.literal("th")


def write_uint(mut writer: Writer, value: Int):
    if value == 0:
        writer.byte(UInt8(48))
        return
    var divisor = 1
    var remaining = value
    while remaining // divisor >= 10:
        divisor *= 10
    while divisor > 0:
        writer.byte(UInt8(48 + (remaining // divisor) % 10))
        divisor //= 10


def write_ordinal_num(mut writer: Writer, value: Int):
    write_uint(writer, value)
    var last_two = value % 100
    if last_two >= 11 and last_two <= 13:
        writer.literal("th")
    elif value % 10 == 1:
        writer.literal("st")
    elif value % 10 == 2:
        writer.literal("nd")
    elif value % 10 == 3:
        writer.literal("rd")
    else:
        writer.literal("th")


def write_year(mut writer: Writer, value: Int):
    var high = value // 100
    var low = value % 100
    if high == 0 or (high % 10 == 0 and low < 10) or high >= 100:
        write_cardinal_positive(writer, value)
        return
    write_cardinal_positive(writer, high)
    writer.byte(UInt8(32))
    if low == 0:
        writer.literal("hundred")
    elif low < 10:
        writer.literal("oh-")
        write_cardinal_positive(writer, low)
    else:
        write_cardinal_positive(writer, low)


@export("mnw_convert_i64")
def mnw_convert_i64(
    values_addr: Int,
    count: Int,
    mode: Int,
    dst_addr: Int,
    stride: Int,
    lengths_addr: Int,
) abi("C") -> Int:
    if count < 0 or stride <= 0 or mode < 0 or mode > 3:
        return -2
    if count == 0:
        return 0
    if values_addr <= 0 or dst_addr <= 0 or lengths_addr <= 0:
        return -2
    var max_address = 9223372036854775807
    if count > max_address // 8 or count > max_address // stride:
        return -2
    var integer_bytes = count * 8
    var output_bytes = count * stride
    if (
        values_addr > max_address - integer_bytes
        or lengths_addr > max_address - integer_bytes
        or dst_addr > max_address - output_bytes
    ):
        return -2
    var values = IPtr(unsafe_from_address=values_addr)
    var lengths = IPtr(unsafe_from_address=lengths_addr)
    for row in range(count):
        var value = Int(values[row])
        var writer = Writer(dst_addr + row * stride, stride)
        if mode == 0:
            if value == -9223372036854775808:
                return -4
            write_cardinal(writer, value)
        elif mode == 1:
            if value < 0:
                return -3
            write_ordinal(writer, value)
        elif mode == 2:
            if value < 0:
                return -3
            write_ordinal_num(writer, value)
        else:
            if value < 0:
                return -3
            write_year(writer, value)
        if writer.position > stride:
            return -1
        lengths[row] = Int64(writer.position)
    return 0
