# Написано на python 3.7
import sys  # библиотека, необходимая для обработки параметра командной строки


def int_to_byte(ivalue, signed=True):
    '''преобразование python int в 4-байтный bytearray'''
    try:
        bvalue = bytearray(int.to_bytes(ivalue, 4, byteorder='big', signed=signed))
    except OverflowError:  # при переполнении старшие биты отбрасываются
        bvalue = bytearray(int.to_bytes(int(format(ivalue, '0b')[-32:], base=2), 4, byteorder='big', signed=signed))
    return bvalue


def byte_to_int(bvalue, signed=True):
    '''преобразование 4-байтного bytearray в python int'''
    return int.from_bytes(bvalue, byteorder='big', signed=signed)


class Processor(object):
    '''процессор'''
    def __init__(self, program=None, data=None):
        self.reg = [bytearray(4), bytearray(4), bytearray(4), bytearray(4), bytearray(4),
                    bytearray(4), bytearray(4), bytearray(4), bytearray(4), bytearray(4),
                    ]  # массив 32 битных регистров (10 регистров)
        if program is None:
            self.cmem = []  # память команд
            for idx in range(256):
                self.cmem.append(bytearray(4))
            self.cmem[0] = int_to_byte(0b11111100_00000000_00000000_00000000, signed=False)
        else:
            self.init_cmem(program)
        if data is None:
            self.dmem = []  # память данных
            for idx in range(10):
                self.dmem.append(bytearray(4))
        else:
            self.init_dmem(data)
        self.pc = 0  # счетчик команд
        self.halt = False  # флаг останова

    def __str__(self):  # вывод текущих данных процессора
        s = 'pc: %d\n' % self.pc
        s += 'Регистры: [\n%s]\n' % (
            str.join(',\n', [format(byte_to_int(regvalue), '#034b') for regvalue in self.reg]))
        s += 'Память данных: [\n%s]\n' % (
            str.join(',\n', [format(byte_to_int(memvalue), '#034b') for memvalue in self.dmem]))
        #s += 'Память команд: [\n%s]\n' % (
        #    str.join(',\n', [format(byte_to_int(memvalue), '#035b') for memvalue in self.cmem]))
        return s

    def __repr__(self):
        return str(self)

    def init_cmem(self, program):
        ''''''
        self.cmem = []
        for idx in range(len(program)):
            self.cmem.append(int_to_byte(program[idx], signed=False))

    def init_dmem(self, data):
        '''запись памяти данных в процессор'''
        self.dmem = []
        for idx in range(len(data)):
            self.dmem.append(int_to_byte(data[idx]))

    def decode_op_type(self, cmd, opnum):
        '''определение типа операнда № opnum'''
        optype = ((cmd >> 24) & 0b11) if opnum == 1 else ((cmd >> 22) & 0b11) if opnum == 2 else None
        if optype is None:
            raise RuntimeError('Некорректный номер операнда')
        return optype

    def read_value(self, src, optype):
        '''чтение значения из источника src типа адресации optype'''
        if optype == 0b00:
            return src
        elif optype == 0b01:
            return byte_to_int(self.reg[src])
        elif optype == 0b10:
            return byte_to_int(self.dmem[src])
        elif optype == 0b11:
            return byte_to_int(self.dmem[byte_to_int(self.reg[src])])
        else:
            raise RuntimeError('Некорректный тип адресации операнда')

    def write_value(self, dst, value, optype):
        '''запись значения value в приемник dst типа адресации optype'''
        if optype == 0b01:
            self.reg[dst] = int_to_byte(value)
        elif optype == 0b10:
            self.dmem[dst] = int_to_byte(value)
        elif optype == 0b11:
            self.dmem[byte_to_int(self.reg[dst])] = int_to_byte(value)
        else:
            raise RuntimeError('Некорректный тип адресации операнда')


class CmdProcessor(object):
    '''обработчик команд процессора'''
    def __init__(self, program=None, data=None):
        self.proc = Processor(program, data)  # процессор
        self.kops = {  # словарь кодов команд {код: (имя, обработчик, к-во операндов, тип операнда1, тип операнда2)}
            0b000000: ('NOP', self.nop_handler, 0),  # No-OP пустая команда
            0b000001: ('MOV', self.mov_handler, 2, 'RMX', 'IRMX'),  # пересылка
            0b000010: ('ADD', self.add_handler, 2, 'RMX', 'IRMX'),  # +
            0b000011: ('SUB', self.sub_handler, 2, 'RMX', 'IRMX'),  # -
            0b000100: ('AND', self.and_handler, 2, 'RMX', 'IRMX'),  # &
            0b000101: ('OR', self.or_handler, 2, 'RMX', 'IRMX'),  # |
            0b000110: ('XOR', self.xor_handler, 2, 'RMX', 'IRMX'),  # ^
            0b000111: ('NOT', self.not_handler, 1, 'RMX'),  # !
            0b001000: ('CMP', self.cmp_handler, 2, 'IRMX', 'IRMX'),  # сравнение
            0b001001: ('JMP', self.jmp_handler, 1, 'I'),  # безусловный переход
            0b001010: ('JE', self.je_handler, 1, 'I'),  # переход по равно 0
            0b001011: ('JG', self.jg_handler, 1, 'I'),  # переход по >
            0b010000: ('OUT', self.out_handler, 1, 'IRMX'),  # вывод значения на устойство вывода
            0b111111: ('HALT', self.halt_handler, 0)  # останов выполнения программы
        }
        self.optypes = {  # мнемоники типов операнда
            'I': 0b00,  # непосредственное значение
            'R': 0b01,  # доступ к регистру по номеру
            'M': 0b10,  # доступ к ячейке памяти по номеру
            'X': 0b11  # доступ к ячейке памяти по номеру регистра, в котором хранится номер ячейки
        }

    def __str__(self):  # вывод текущих данных процессора
        return str(self.proc)

    def __repr__(self):
        return str(self)

    def assemble(self, asmprog, code_section_start_idx=0):
        '''перевод программы на языке ассемблера в машинные коды'''
        commands = {v[0]: k for k, v in self.kops.items()}  # словарь имен команд {имя: код}
        labels = {}  # словарь меток программы {метка: адрес метки}
        labels_to_patch = {}  # словарь неопределенных меток для бэкпатчинга {адрес команды перехода к метке: метка}
        prog = []  # программа в машинных кодах процессора
        for idx in range(code_section_start_idx, len(asmprog)):
            if asmprog[idx] == '':  # пропуск пустых строк
                continue
            cmd = int(0)  # текущая команда в машинных кодах
            asmcmd = str.split(asmprog[idx])  # разбиение asm команды на компоненты
            if len(asmcmd) < 1:
                raise RuntimeError('Синтаксическая ошибка в строке %d.' % (idx + 1))
            if asmcmd[0].strip().endswith(':'):  # обработка метки команды
                label = asmcmd[0].replace(':', '')  # получение имени метки
                if label in labels:
                    raise RuntimeError('Синтаксическая ошибка в строке %d. Повторное объявление метки.' % (idx + 1))
                labels[label] = len(prog)  # сохранение адреса метки
                asmcmd.remove(asmcmd[0])  # удаление метки для дальнейшего разбора команды
            if len(asmcmd) < 1:
                raise RuntimeError('Синтаксическая ошибка в строке %d.' % (idx + 1))
            if str.upper(asmcmd[0]) not in commands:
                raise RuntimeError('Синтаксическая ошибка в строке %d. Неизвестная команда.' % (idx + 1))
            kop = commands[str.upper(asmcmd[0])]  # код команды
            cmd |= kop << 26  # запись кода команды
            opcount = self.kops[kop][2]  # количество операндов команды
            if opcount > 0:
                if asmcmd[0].upper().startswith('J'):  # обработка команды перехода
                    if opcount != len(asmcmd) - 1:  # неверное количество операндов
                        raise RuntimeError(
                            'Синтаксическая ошибка в строке %d. Некорректное количество операндов.' % (idx + 1))
                    if asmcmd[1] in labels:  # если адрес метки уже сохранен
                        cmd |= self.optypes['I'] << 24  # запись типа операнда команды перехода
                        cmd |= labels[asmcmd[1]] << 8  # запись операнда - адреса перехода к метке
                    else:  # добавление команды в словарь для бэкпатчинга
                        labels_to_patch[len(prog)] = asmcmd[1]
                else:
                    # обработка остальных команд
                    if opcount != len(asmcmd) - 2:  # неверное количество операндов
                        raise RuntimeError(
                            'Синтаксическая ошибка в строке %d. Некорректное количество операндов.' % (idx + 1))
                    if len(asmcmd[1]) != opcount:
                        raise RuntimeError(
                            'Синтаксическая ошибка в строке %d. Некорректный идентификатор типов операндов.' %
                            (idx + 1))
                    if asmcmd[1][0] not in self.kops[kop][3]:
                        raise RuntimeError(
                            'Синтаксическая ошибка в строке %d. Некорректный идентификатор типа первого операнда.' %
                            (idx + 1))
                    cmd |= self.optypes[asmcmd[1][0]] << 24  # запись типа первого операнда
                    if not str.isdecimal(asmcmd[2]):
                        raise RuntimeError(
                            'Синтаксическая ошибка в строке %d. Некорректный первый операнд.' % (idx + 1))
                    cmd |= int(asmcmd[2]) << 8  # запись первого операнда
                    if opcount == 2:
                        if len(asmcmd[1]) != 2 or asmcmd[1][1] not in self.kops[kop][4]:
                            raise RuntimeError(
                                'Синтаксическая ошибка в строке %d. Некорректный идентификатор типа второго операнда.' %
                                (idx + 1))
                        cmd |= self.optypes[asmcmd[1][1]] << 22  # запись типа второго операнда
                        if not str.isdecimal(asmcmd[3]):
                            raise RuntimeError(
                                'Синтаксическая ошибка в строке %d. Некорректный второй операнд.' % (idx + 1))
                        cmd |= int(asmcmd[3])  # запись второго операнда
            prog.append(cmd)  # добавление закодированной команды в программу в машинных кодах
        if len(labels_to_patch) > 0:  # если есть неопределенные метки
            for addr, label in labels_to_patch.items():  # проход по программе и проставление адресов меток
                if label not in labels:
                    raise RuntimeError('Неизвестная метка %s.' % label)
                cmd = prog[addr]
                cmd |= self.optypes['I'] << 24  # запись типа операнда команды перехода
                cmd |= labels[label] << 8  # запись операнда - адреса перехода к метке
                prog[addr] = cmd
        self.proc.init_cmem(prog)  # запись программы в память процессора
        return prog

    def open_asm_file(self, filename):
        '''чтение asm кода из файла'''
        with open(filename, 'r') as inputFile:  # открытие входного файла
            src = inputFile.readlines()  # строки исходного файла
            if len(src) == 0:
                raise RuntimeError('Исходный файл пуст.')
            src = [line.strip() for line in src]  # удаление символов перевода строк

            # удаление комментариев (# ...)
            src = [line[0:(len(line) if line.find('#') == -1 else line.find('#'))].strip() for line in src]
            strptr = 0  # счетчик строк исходного файла
            if src[strptr] == '.data':  # разбор секции данных
                i = strptr + 1
                self.proc.dmem = []
                while i < len(src) and src[i] != '.code':
                    if src[i] == '':  # пропуск пустых строк
                        i += 1
                        continue
                    try:
                        self.proc.dmem.append(int_to_byte(int(src[i], 0)))
                    except Exception:
                        raise RuntimeError('Синтаксическая ошибка в строке %d.' % (i + 1))
                    i += 1
                strptr = i
            asmprogram = ''
            mashprog = []
            if src[strptr] == '.code':  # разбор секции программы
                strptr += 1
                if strptr >= len(src) - 1:
                    raise RuntimeError('В исходном файле отсутствует программа.')
                asmprogram = str.join('\n', src[strptr:])  # сохранение текста asm программы
                mashprog = self.assemble(src, strptr)  # ассемблирование asm программы
            else:
                raise RuntimeError('В исходном файле отсутствует программа.')
            return asmprogram, mashprog

    def run(self):
        '''запуск программы на выполнение'''
        print(self)
        while not self.proc.halt:
            self.execute_cmd()
            print(self)

    def execute_cmd(self):
        '''выбор и выполнение команды'''
        cmd = byte_to_int(self.proc.cmem[self.proc.pc], signed=False)  # получение очередной команды
        kop = (cmd >> 26) & 0x3f  # код команды (6 бит, 31-26)
        if kop not in self.kops:
            raise RuntimeError('Некорректный код команды (pc = %d).' % self.proc.pc)
        self.kops[kop][1](cmd)  # выполнение команды

    def nop_handler(self, cmd):
        '''обработчик пустой команды'''
        pass

    def mov_handler(self, cmd):
        '''обработчик команды пересылки'''
        optype1 = self.proc.decode_op_type(cmd, 1)  # тип адресации приемника
        optype2 = self.proc.decode_op_type(cmd, 2)  # тип адресации источника
        value = self.proc.read_value(cmd & 0xff, optype2)  # извлечение значения (адрес источника/непосредственное)
        self.proc.write_value((cmd >> 8) & 0xff, value, optype1)  # запись значения в приемник
        self.proc.pc += 1

    def add_handler(self, cmd):
        '''обработчик команды сложения (приемник = приемник + источник)'''
        optype1 = self.proc.decode_op_type(cmd, 1)  # тип адресации приемника
        optype2 = self.proc.decode_op_type(cmd, 2)  # тип адресации источника
        value1 = self.proc.read_value((cmd >> 8) & 0xff, optype1)  # извлечение значения приемника
        value2 = self.proc.read_value(cmd & 0xff, optype2)  # извлечение значения источника/непосредственное значение
        self.proc.write_value(
            (cmd >> 8) & 0xff, value1 + value2, optype1)  # запись значения в приемник
        self.proc.pc += 1

    def sub_handler(self, cmd):
        '''обработчик команды вычитания (приемник = приемник - источник)'''
        optype1 = self.proc.decode_op_type(cmd, 1)  # тип адресации приемника
        optype2 = self.proc.decode_op_type(cmd, 2)  # тип адресации источника
        value1 = self.proc.read_value((cmd >> 8) & 0xff, optype1)  # извлечение значения приемника
        value2 = self.proc.read_value(cmd & 0xff, optype2)  # извлечение значения источника/непосредственное значение
        self.proc.write_value(
            (cmd >> 8) & 0xff, value1 - value2, optype1)  # запись значения в приемник
        self.proc.pc += 1

    def and_handler(self, cmd):
        '''обработчик команды побитового И (приемник = приемник & источник)'''
        optype1 = self.proc.decode_op_type(cmd, 1)  # тип адресации приемника
        optype2 = self.proc.decode_op_type(cmd, 2)  # тип адресации источника
        value1 = self.proc.read_value((cmd >> 8) & 0xff, optype1)  # извлечение значения приемника
        value2 = self.proc.read_value(cmd & 0xff, optype2)  # извлечение значения источника/непосредственное значение
        self.proc.write_value(
            (cmd >> 8) & 0xff, value1 & value2, optype1)  # запись значения в приемник
        self.proc.pc += 1

    def or_handler(self, cmd):
        '''обработчик команды побитового ИЛИ (приемник = приемник | источник)'''
        optype1 = self.proc.decode_op_type(cmd, 1)  # тип адресации приемника
        optype2 = self.proc.decode_op_type(cmd, 2)  # тип адресации источника
        value1 = self.proc.read_value((cmd >> 8) & 0xff, optype1)  # извлечение значения приемника
        value2 = self.proc.read_value(cmd & 0xff, optype2)  # извлечение значения источника/непосредственное значение
        self.proc.write_value(
            (cmd >> 8) & 0xff, value1 | value2, optype1)  # запись значения в приемник
        self.proc.pc += 1

    def xor_handler(self, cmd):
        '''обработчик команды побитового исключающего ИЛИ (приемник = приемник ^ источник)'''
        optype1 = self.proc.decode_op_type(cmd, 1)  # тип адресации приемника
        optype2 = self.proc.decode_op_type(cmd, 2)  # тип адресации источника
        value1 = self.proc.read_value((cmd >> 8) & 0xff, optype1)  # извлечение значения приемника
        value2 = self.proc.read_value(cmd & 0xff, optype2)  # извлечение значения источника/непосредственное значение
        self.proc.write_value(
            (cmd >> 8) & 0xff, value1 ^ value2, optype1)  # запись значения в приемник
        self.proc.pc += 1

    def not_handler(self, cmd):
        '''обработчик команды  побитового НЕ (приемник = !приемник)'''
        optype1 = self.proc.decode_op_type(cmd, 1)  # тип адресации приемника
        value1 = self.proc.read_value((cmd >> 8) & 0xff, optype1)  # извлечение значения приемника
        self.proc.write_value(
            (cmd >> 8) & 0xff, ~value1, optype1)  # запись значения в приемник
        self.proc.pc += 1

    def cmp_handler(self, cmd):
        '''обработчик команды сравнения, результат сравнения в регистре reg[0]'''
        optype1 = self.proc.decode_op_type(cmd, 1)  # тип адресации первого операнда
        optype2 = self.proc.decode_op_type(cmd, 2)  # тип адресации второго операнда
        value1 = self.proc.read_value((cmd >> 8) & 0xff, optype1)  # извлечение значения первого операнда
        value2 = self.proc.read_value(
            cmd & 0xff, optype2)  # извлечение значения второго операнда/непосредственное значение
        if value1 > value2:
            self.proc.write_value(0, 0b10, 0b01)  # >, запись результата сравнения в регистр reg[0]
        elif value1 < value2:
            self.proc.write_value(0, 0b01, 0b01)  # <
        else:
            self.proc.write_value(0, 0b00, 0b01)  # ==
        self.proc.pc += 1

    def jmp_handler(self, cmd):
        '''обработчик команды безусловного перехода'''
        optype1 = self.proc.decode_op_type(cmd, 1)  # тип адресации первого операнда
        value1 = self.proc.read_value((cmd >> 8) & 0xff, optype1)  # извлечение значения первого операнда
        self.proc.pc = value1

    def je_handler(self, cmd):
        '''обработчик команды перехода по равенству 0'''
        optype1 = self.proc.decode_op_type(cmd, 1)  # тип адресации первого операнда
        value1 = self.proc.read_value((cmd >> 8) & 0xff, optype1)  # извлечение значения первого операнда
        reg0value = self.proc.read_value(0, 0b01)  # значение регистра reg[0]
        if reg0value == 0b00:
            self.proc.pc = value1
        else:
            self.proc.pc += 1

    def jg_handler(self, cmd):
        '''обработчик команды перехода по >'''
        optype1 = self.proc.decode_op_type(cmd, 1)  # тип адресации первого операнда
        value1 = self.proc.read_value((cmd >> 8) & 0xff, optype1)  # извлечение значения первого операнда
        reg0value = self.proc.read_value(0, 0b01)  # значение регистра reg[0]
        if reg0value == 0b10:
            self.proc.pc = value1
        else:
            self.proc.pc += 1

    def out_handler(self, cmd):
        '''обработчик команды вывода значения на устойство вывода (на экран)'''
        optype1 = self.proc.decode_op_type(cmd, 1)  # тип адресации источника
        value1 = self.proc.read_value((cmd >> 8) & 0xff, optype1)  # извлечение значения источника
        print('Output: %d' % value1)  # вывод значения
        self.proc.pc += 1

    def halt_handler(self, cmd):
        '''обработчик команды останова'''
        self.proc.halt = True
        self.proc.pc += 1


if __name__ == '__main__':  # точка входа в программу
    fileName = ''
    if len(sys.argv) == 2:  # имя исходного файла передано в параметре командной строки
        try:
            with open(sys.argv[1], 'r'):
                fileName = sys.argv[1]
        except FileNotFoundError as e:
            print(f'Ошибка: указан несуществующий файл "{e.filename}"')
        except PermissionError as e:
            print(f'Ошибка: отказано в доступе к файлу "{e.filename}"')
    if fileName == '':  # запрос ввода имени исходного файла с клавиатуры
        fileName = input('Введите имя входного файла: ')
        try:
            with open(fileName, 'r'):
                pass
        except FileNotFoundError as e:
            fileName = ''
            print(f'Ошибка: указан несуществующий файл "{e.filename}"')
        except PermissionError as e:
            fileName = ''
            print(f'Ошибка: отказано в доступе к файлу "{e.filename}"')

    if fileName != '':
        proc = CmdProcessor(None, None)  # инициализация эмулятора
        try:
            asmprogram, mashprog = proc.open_asm_file(fileName)
            print('Исходная программа в коде ассемблера:\n' + asmprogram + '\n')
            print('Программа в машинных кодах:')
            print(str.join(',\n', [format(cmd, '#034b') for cmd in mashprog]))

            print('Протокол эмуляции.')
            proc.run()  # запуск эмуляции
        except RuntimeError as err:
            print(err.args[0])
