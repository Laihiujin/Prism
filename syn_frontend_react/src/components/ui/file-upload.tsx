import { cn } from "@/lib/utils";
import React, { useRef, useState } from "react";
import { motion } from "framer-motion";
import { IconUpload } from "@tabler/icons-react";
import { useDropzone } from "react-dropzone";
import { X } from "lucide-react";

const mainVariant = {
    initial: {
        x: 0,
        y: 0,
    },
    animate: {
        x: 20,
        y: -20,
        opacity: 0.9,
    },
};

const secondaryVariant = {
    initial: {
        opacity: 0,
    },
    animate: {
        opacity: 1,
    },
};

export const FileUpload = ({
    onChange,
}: {
    onChange?: (files: File[]) => void;
}) => {
    const [files, setFiles] = useState<File[]>([]);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleFileChange = (newFiles: File[]) => {
        const updatedFiles = [...files, ...newFiles];
        setFiles(updatedFiles);
        onChange && onChange(updatedFiles);
    };

    const handleRemoveFile = (index: number) => {
        const updatedFiles = files.filter((_, i) => i !== index);
        setFiles(updatedFiles);
        onChange && onChange(updatedFiles);
    };

    const onDrop = (acceptedFiles: File[]) => {
        handleFileChange(acceptedFiles);
    };

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        multiple: true,
    });

    return (
        <div className="w-full" {...getRootProps()}>
            <motion.div
                onClick={() => fileInputRef.current?.click()}
                whileHover="animate"
                className={cn(
                    "group/file block w-full relative overflow-hidden cursor-pointer",
                    "rounded-xl border border-dashed border-white/10 bg-black",
                    "p-6 md:p-8 min-h-[220px]",
                    "hover:border-white/20 transition-colors"
                )}
            >
                <input
                    {...getInputProps()}
                    ref={fileInputRef}
                    id="file-upload-handle"
                    className="hidden"
                />
                <div className="absolute inset-0 opacity-25 [mask-image:radial-gradient(ellipse_at_center,white,transparent)] pointer-events-none">
                    <GridPattern />
                </div>
                <div className="flex flex-col items-center justify-center">
                    <p className="relative z-20 font-sans font-semibold text-white/90 text-base">
                        上传素材
                    </p>
                    <p className="relative z-20 font-sans font-normal text-white/50 text-sm mt-2">
                        拖拽文件到此处或点击上传
                    </p>
                    <div className="relative w-full mt-10 max-w-xl mx-auto">
                        {files.length > 0 && (
                            <motion.div
                                key="file-0"
                                layoutId="file-upload"
                                className={cn(
                                    "relative overflow-hidden z-40 bg-white/5 flex flex-col items-start justify-start p-4 mt-4 w-full mx-auto rounded-xl",
                                    "border border-white/10"
                                )}
                            >
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleRemoveFile(0);
                                    }}
                                    className="absolute top-2 right-2 z-50 h-7 w-7 rounded-full bg-white/10 hover:bg-white/15 flex items-center justify-center text-white transition-colors"
                                >
                                    <X className="h-4 w-4" />
                                </button>
                                <div className="flex w-full items-center gap-3 pr-8 min-w-0">
                                    <motion.p
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        layout
                                        className="text-sm text-white/80 truncate flex-1 min-w-0"
                                    >
                                        {files[0].name}
                                    </motion.p>
                                    <motion.p
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        layout
                                        className="rounded-lg px-2 py-1 w-fit flex-shrink-0 text-xs text-white/70 bg-white/10"
                                    >
                                        {(files[0].size / (1024 * 1024)).toFixed(2)} MB
                                    </motion.p>
                                </div>
                                {files.length > 1 && (
                                    <motion.p
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        className="text-xs text-white/50 mt-2"
                                    >
                                        +{files.length - 1} 个文件
                                    </motion.p>
                                )}
                            </motion.div>
                        )}
                        {!files.length && (
                            <motion.div
                                layoutId="file-upload"
                                variants={mainVariant}
                                transition={{
                                    type: "spring",
                                    stiffness: 300,
                                    damping: 20,
                                }}
                                className={cn(
                                    "relative group-hover/file:shadow-2xl z-40 bg-white/5 flex items-center justify-center h-36 mt-4 w-full max-w-[10rem] mx-auto rounded-xl",
                                    "border border-white/10"
                                )}
                            >
                                {isDragActive ? (
                                    <motion.p
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        className="text-white/80 flex flex-col items-center text-sm"
                                    >
                                        松开上传
                                        <IconUpload className="h-4 w-4 text-white/70" />
                                    </motion.p>
                                ) : (
                                    <IconUpload className="h-5 w-5 text-white/70" />
                                )}
                            </motion.div>
                        )}

                        {!files.length && (
                            <motion.div
                                variants={secondaryVariant}
                                className="absolute opacity-0 border border-dashed border-white/25 inset-0 z-30 bg-transparent flex items-center justify-center h-36 mt-4 w-full max-w-[10rem] mx-auto rounded-xl"
                            ></motion.div>
                        )}
                    </div>
                </div>
            </motion.div>
        </div>
    );
};

export function GridPattern() {
    const columns = 41;
    const rows = 11;
    return (
        <div className="flex bg-transparent flex-shrink-0 flex-wrap justify-center items-center gap-x-px gap-y-px scale-105">
            {Array.from({ length: rows }).map((_, row) =>
                Array.from({ length: columns }).map((_, col) => {
                    const index = row * columns + col;
                    return (
                        <div
                            key={`${col}-${row}`}
                            className={cn(
                                "w-10 h-10 flex flex-shrink-0 rounded-[2px]",
                                index % 2 === 0
                                    ? "bg-white/[0.015]"
                                    : "bg-white/[0.015] shadow-[0px_0px_0px_1px_rgba(255,255,255,0.03)_inset]"
                            )}
                        />
                    );
                })
            )}
        </div>
    );
}
