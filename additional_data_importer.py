import sys

from api.importer import TemplateImporter

if __name__ == '__main__':
    args = sys.argv
    # print(args)
    addi = TemplateImporter(data=args[1])
    # print(addi.data_type)
    addi.run(args[2])
